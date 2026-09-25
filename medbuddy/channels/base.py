"""The transport interface + the normalized inbound-message type."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class IncomingMessage:
    """A message from a patient, normalized across channels."""

    sender: str  # channel-specific id (e.g. "whatsapp:+9199...")
    text: str | None = None
    media_url: str | None = None  # image URL (Twilio)
    media_bytes: bytes | None = None  # raw image bytes (fake channel / local files)

    @property
    def has_image(self) -> bool:
        return bool(self.media_url or self.media_bytes)


class MessagingChannel(Protocol):
    """Outbound transport. Implementations: FakeChannel (dev/tests), TwilioChannel (prod)."""

    def send_text(self, to: str, text: str) -> None: ...
