"""A mockable clock so reminder timing (and Twilio's 3-day expiry) can be tested fast.

Inject a `Clock` everywhere time is read; use `RealClock` in production and `FakeClock`
in tests to advance time deterministically without waiting.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class RealClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FakeClock:
    """Manually-advanced clock for deterministic tests."""

    def __init__(self, start: datetime):
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, **timedelta_kwargs) -> None:
        """e.g. clock.advance(hours=8) or clock.advance(days=3)."""
        self._now = self._now + timedelta(**timedelta_kwargs)
