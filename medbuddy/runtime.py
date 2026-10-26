"""Shared singletons: LLM client, agent, channel, clock.

Both the FastAPI app and the CLI build their dependencies here so behaviour matches.
The browser chat is the sole application transport. FakeChannel remains available in tests
and in the local CLI.
"""
from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from medbuddy.agent import Agent
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
    from medbuddy.channels.web import WebChannel

    return WebChannel()
