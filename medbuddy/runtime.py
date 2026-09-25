"""Shared singletons: LLM client, agent, channel, clock.

Both the FastAPI app and the CLI build their dependencies here so behaviour matches.
Channel is chosen from settings.CHANNEL (fake by default -> zero Twilio credits).
"""
from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from medbuddy.agent import Agent
from medbuddy.channels import FakeChannel
from medbuddy.config import get_settings
from medbuddy.llm import LLMClient
from medbuddy.scheduler.clock import RealClock

if TYPE_CHECKING:
    from medbuddy.channels import MessagingChannel
    from medbuddy.scheduler.clock import Clock


@lru_cache
def get_llm() -> LLMClient:
    return LLMClient()


@lru_cache
def get_agent() -> Agent:
    return Agent(get_llm())


@lru_cache
def get_clock() -> "Clock":
    return RealClock()


@lru_cache
def get_channel() -> "MessagingChannel":
    settings = get_settings()
    if settings.channel == "twilio":
        from medbuddy.channels.twilio import TwilioChannel

        return TwilioChannel(
            settings.twilio_account_sid,
            settings.twilio_auth_token,
            settings.twilio_whatsapp_from,
        )
    return FakeChannel(echo=False)
