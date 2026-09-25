"""Thin, provider-agnostic wrapper over LiteLLM.

Why this exists (and why it is *not* the Anthropic SDK): MedBuddy must run its core
LLM across OpenAI / Anthropic / Groq / Gemini / OpenRouter (incl. free models) by
changing a model string, not code. LiteLLM gives one OpenAI-style surface to all of them.

Model is chosen per *role*, because the three jobs have different needs:
  • "agent"       — the orchestration/tool-use loop; needs reliable function-calling.
  • "vision"      — image -> structured extraction; needs a vision-capable model.
  • "explanation" — plain-language drug info; cheap/free models are fine here.

Provider API keys are read from settings and exported to os.environ, which is where
LiteLLM looks for them.
"""
from __future__ import annotations

import base64
import os
import random
import time
from typing import Any, Literal

from medbuddy.config import Settings, get_settings

Role = Literal["agent", "vision", "explanation"]


class LLMClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        # LiteLLM reads provider credentials from the environment.
        for name, value in self.settings.provider_keys().items():
            os.environ.setdefault(name, value)

    def model_for(self, role: Role) -> str:
        return {
            "agent": self.settings.agent_model,
            "vision": self.settings.vision_model,
            "explanation": self.settings.explanation_model,
        }.get(role, self.settings.agent_model)

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        role: Role = "agent",
        tools: list[dict] | None = None,
        tool_choice: str = "auto",
        temperature: float = 0.2,
        **kwargs: Any,
    ) -> Any:
        """One chat completion. Returns LiteLLM's ModelResponse (OpenAI-shaped).

        Tries the role's model first, then each entry in LLM_FALLBACKS in order.
        Each model gets up to MAX_ATTEMPTS tries with exponential backoff before we
        give up on it and move to the next fallback.
        """
        import litellm

        MAX_ATTEMPTS = 4
        BASE_DELAY = 1.0
        MAX_DELAY = 30.0

        def _is_retryable(err: Exception) -> bool:
            msg = str(err).lower()
            return any(s in msg for s in (
                "429", "rate limit", "resource exhausted",
                "quota", "503", "502", "unavailable", "timeout",
            ))

        models = [self.model_for(role), *self.settings.fallback_models]
        last_err: Exception | None = None

        for model in models:
            params: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                **kwargs,
            }
            if tools:
                params["tools"] = tools
                params["tool_choice"] = tool_choice

            for attempt in range(MAX_ATTEMPTS):
                try:
                    return litellm.completion(**params)
                except Exception as err:  # noqa: BLE001
                    if _is_retryable(err) and attempt < MAX_ATTEMPTS - 1:
                        delay = min(BASE_DELAY * (2 ** attempt) + random.uniform(0, 1), MAX_DELAY)
                        time.sleep(delay)
                        last_err = err
                    else:
                        last_err = err
                        break

        assert last_err is not None
        raise last_err

    def text(
        self,
        prompt: str,
        *,
        role: Role = "explanation",
        system: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        """Convenience: prompt in, plain string out."""
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = self.complete(messages, role=role, temperature=temperature)
        return resp.choices[0].message.content or ""

    @staticmethod
    def image_message(
        prompt: str,
        *,
        image_url: str | None = None,
        image_bytes: bytes | None = None,
        mime: str = "image/png",
    ) -> dict[str, Any]:
        """Build a multimodal user message (text + one image) for vision models."""
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if image_bytes is not None:
            b64 = base64.b64encode(image_bytes).decode()
            image_url = f"data:{mime};base64,{b64}"
        if image_url:
            content.append({"type": "image_url", "image_url": {"url": image_url}})
        return {"role": "user", "content": content}