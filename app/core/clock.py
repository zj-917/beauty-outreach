"""Time source abstraction; the only module allowed to read the system clock."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    """Injectable time source."""

    def now(self) -> datetime:
        """Return the current UTC time."""
        ...

    def monotonic(self) -> float:
        """Return a monotonic counter in seconds."""
        ...

    def sleep(self, seconds: float) -> None:
        """Wait for the given number of seconds."""
        ...


class SystemClock:
    """Wall-clock implementation backed by the standard library."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class FakeClock:
    """Deterministic clock for tests."""

    def __init__(self, start: datetime | None = None) -> None:
        if start is None:
            start = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)
        if start.tzinfo is None:
            raise ValueError("FakeClock start must be timezone-aware")
        self._now = start.astimezone(UTC)
        self._monotonic = 0.0

    def now(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._monotonic

    def sleep(self, seconds: float) -> None:
        self.advance(seconds)

    def advance(self, seconds: float) -> None:
        """Move time forward by the given number of seconds."""
        if seconds < 0:
            raise ValueError("cannot move time backwards")
        self._monotonic += seconds
        self._now = self._now + timedelta(seconds=seconds)

    def set(self, value: datetime) -> None:
        """Set the wall clock explicitly."""
        if value.tzinfo is None:
            raise ValueError("FakeClock set requires a timezone-aware datetime")
        self._now = value.astimezone(UTC)
