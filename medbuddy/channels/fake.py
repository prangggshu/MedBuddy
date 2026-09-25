"""In-memory channel: records outbound messages instead of sending them. Zero credits."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SentMessage:
    to: str
    text: str


class FakeChannel:
    """Drop-in `MessagingChannel` for development, the CLI, and tests.

    Captures everything MedBuddy would send in `outbox`; optionally echoes to stdout.
    """

    def __init__(self, echo: bool = False):
        self.outbox: list[SentMessage] = []
        self.echo = echo

    def send_text(self, to: str, text: str) -> None:
        self.outbox.append(SentMessage(to=to, text=text))
        if self.echo:
            print(f"\n🤖 MedBuddy → {to}:\n{text}\n")

    def last(self) -> SentMessage | None:
        return self.outbox[-1] if self.outbox else None
