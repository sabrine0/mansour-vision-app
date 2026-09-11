"""Time.

Every timestamp that crosses a service boundary, reaches the database, or lands
in an evidence manifest is timezone-aware UTC. Volume II ADM-006 makes clock
handling a safety concern: an evidence pack built on ambiguous timestamps is
worthless, and a naive datetime is ambiguous by construction.

`ruff`'s DTZ rules ban naive datetime construction repo-wide. This module is the
single sanctioned way to obtain the current time, and `Clock` is the seam that
lets tests control it without patching `datetime` globally.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """A source of the current instant.

    Injected rather than called directly so that time-dependent logic — alert
    cooldowns, occupancy anchor ages, stream deduplication windows — is testable
    without sleeping.
    """

    def now(self) -> datetime:
        """Return the current instant as a timezone-aware UTC datetime."""
        ...


class SystemClock:
    """The real clock. The only implementation used in production."""

    __slots__ = ()

    def now(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock:
    """A controllable clock for tests.

    Not exported for production use: services take a `Clock`, and only test
    fixtures construct this.
    """

    __slots__ = ("_now",)

    def __init__(self, start: datetime) -> None:
        self._now = _require_aware(start)

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> datetime:
        """Move the clock forward. Returns the new instant."""
        if seconds < 0:
            raise ValueError("FrozenClock cannot move backwards")
        from datetime import timedelta

        self._now = self._now + timedelta(seconds=seconds)
        return self._now

    def set(self, instant: datetime) -> None:
        self._now = _require_aware(instant)


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError("naive datetime rejected: all instants must be timezone-aware UTC")
    return value.astimezone(UTC)


def utcnow() -> datetime:
    """Convenience for code that has no `Clock` to inject (entrypoints, logging)."""
    return datetime.now(UTC)


def to_utc(value: datetime) -> datetime:
    """Normalise an aware datetime to UTC. Rejects naive input rather than guessing."""
    return _require_aware(value)


def isoformat(value: datetime) -> str:
    """Serialise as an explicit-offset ISO-8601 string, always in UTC."""
    return _require_aware(value).isoformat()


__all__ = [
    "Clock",
    "FrozenClock",
    "SystemClock",
    "isoformat",
    "to_utc",
    "utcnow",
]
