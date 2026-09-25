"""Messaging transport abstraction.

Twilio/WhatsApp is just a transport. Everything above this layer works against
`MessagingChannel`, so the whole system runs end-to-end with `FakeChannel` — zero
Twilio credits — and Twilio becomes one adapter added last.
"""
from .base import IncomingMessage, MessagingChannel
from .fake import FakeChannel, SentMessage

__all__ = ["IncomingMessage", "MessagingChannel", "FakeChannel", "SentMessage"]
