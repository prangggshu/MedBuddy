"""Twilio WhatsApp sandbox adapter — wire this LAST (Week 3).

Sandbox constraints to respect (see CLAUDE.md):
  • 100 free messages, then billed
  • sessions expire 3 days after a number sends `join <code>`
  • rate limit ~1 message / 3 seconds  -> queue/delay bursty sends
  • business-initiated messages outside the 24h window need approved templates
"""
from __future__ import annotations

from .base import IncomingMessage


class TwilioChannel:
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self.from_number = from_number
        # TODO(week3): from twilio.rest import Client
        #              self.client = Client(account_sid, auth_token)
        raise NotImplementedError(
            "TwilioChannel is intentionally stubbed until Week 3. Use CHANNEL=fake for now."
        )

    def send_text(self, to: str, text: str) -> None:
        # TODO(week3): self.client.messages.create(from_=self.from_number, to=to, body=text)
        raise NotImplementedError

    @staticmethod
    def parse_incoming(form: dict) -> IncomingMessage:
        """Twilio posts form fields: From, Body, NumMedia, MediaUrl0, ..."""
        # TODO(week3): map form -> IncomingMessage (download MediaUrl0 for images)
        raise NotImplementedError
