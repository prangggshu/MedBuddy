"""Environment-driven settings (see .env.example for documentation of every field)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: str = "dev"

    # ── Database ──────────────────────────────────────────────
    database_url: str = "sqlite:///./medbuddy.db"
    # LangGraph conversation checkpoints live in their own file, so clearing chat state
    # never touches patient data.
    checkpoint_db: str = "./checkpoints.db"

    # ── LLM (LiteLLM model strings), chosen per role ──────────
    agent_model: str = "gemini/gemini-3.8-flash"
    vision_model: str = "gemini/gemini-3.8-flash"
    explanation_model: str = "gemini/gemini-3.8-flash"
    llm_fallbacks: str = ""  # comma-separated model strings

    # Provider API keys — pushed into os.environ for LiteLLM by the LLM client.
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    groq_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""

    # ── Messaging ─────────────────────────────────────────────
    channel: str = "fake"  # "fake" | "twilio"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"

    # ── Reminders ─────────────────────────────────────────────
    missed_dose_window_min: int = 60
    # Patients' local time as a fixed UTC offset (IST = +330, no DST). Reminder times like
    # "09:00" are interpreted in this zone.
    tz_offset_minutes: int = 330

    # ── Agent ─────────────────────────────────────────────────
    # LangGraph steps per inbound message (each agent or tool node counts as one).
    agent_recursion_limit: int = 25
    # Photo replies: "template" = built purely from tool results (1 LLM call per photo);
    # "rephrase" = template rewritten warmly by EXPLANATION_MODEL (2 calls per photo).
    photo_reply_mode: str = "template"

    @property
    def fallback_models(self) -> list[str]:
        return [m.strip() for m in self.llm_fallbacks.split(",") if m.strip()]

    def provider_keys(self) -> dict[str, str]:
        """Env-var name -> value, for the keys that are actually set."""
        mapping = {
            "OPENAI_API_KEY": self.openai_api_key,
            "ANTHROPIC_API_KEY": self.anthropic_api_key,
            "GROQ_API_KEY": self.groq_api_key,
            "GEMINI_API_KEY": self.gemini_api_key,
            "OPENROUTER_API_KEY": self.openrouter_api_key,
        }
        return {k: v for k, v in mapping.items() if v}


@lru_cache
def get_settings() -> Settings:
    return Settings()
