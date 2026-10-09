"""Tool base class + the shared context every tool receives.

In MedBuddy's fully-agentic design, *every* capability is a Tool. The agent loop
(medbuddy/agent/loop.py) decides which to call; this module defines the contract.

A Tool exposes an OpenAI-style function schema (`.schema()`) and a `.run(args, ctx)`
that returns a JSON-serializable dict fed back to the model as the tool result.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from medbuddy.channels import MessagingChannel
    from medbuddy.datasets.loaders import Datasets
    from medbuddy.llm import LLMClient
    from medbuddy.scheduler.clock import Clock


def guess_image_mime(data: bytes) -> str:
    """Sniff the image type from magic bytes (vision APIs reject a mislabelled image)."""
    if data.startswith(bytes((0xFF, 0xD8, 0xFF))):
        return "image/jpeg"
    if data.startswith(bytes((0x89,)) + b"PNG"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1"):
        return "image/heic"
    return "image/jpeg"


@dataclass
class ToolContext:
    """Everything a tool might need, assembled once per inbound message by the loop."""

    sender: str  # current patient's WhatsApp id
    session: "Session"
    llm: "LLMClient"
    datasets: "Datasets"
    clock: "Clock"
    channel: "MessagingChannel"
    pending_image: bytes | None = None  # raw bytes of an image the patient just sent


class Tool:
    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {"type": "object", "properties": {}}

    def run(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        raise NotImplementedError

    def schema(self) -> dict[str, Any]:
        """OpenAI/LiteLLM function-calling spec for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
