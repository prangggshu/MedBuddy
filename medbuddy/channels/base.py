"""The transport interface + the normalized inbound-message type."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class IncomingMessage:
    """A message from a patient, normalized across channels."""

    sender: str  # normalized patient phone identity
    text: str | None = None
    media_url: str | None = None
    media_bytes: bytes | None = None  # raw image bytes for the vision path

    @property
    def has_image(self) -> bool:
        return bool(self.media_url or self.media_bytes)


class MessagingChannel(Protocol):
    """Outbound transport. WebChannel persists chat replies; FakeChannel supports tests."""

    def send_text(self, to: str, text: str) -> None: ...
