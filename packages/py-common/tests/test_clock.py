"""Time is UTC-aware, always. Naive datetimes are rejected, never coerced."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from mansour_common.clock import FrozenClock, SystemClock, isoformat, to_utc, utcnow


def test_system_clock_returns_aware_utc() -> None:
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_utcnow_is_aware() -> None:
    assert utcnow().tzinfo is UTC


def test_to_utc_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="naive datetime rejected"):
        to_utc(datetime(2026, 7, 9, 12, 0, 0))  # noqa: DTZ001 — the point of the test


def test_to_utc_normalises_other_offsets() -> None:
    casablanca = timezone(timedelta(hours=1))
    local = datetime(2026, 7, 9, 13, 0, 0, tzinfo=casablanca)

    normalised = to_utc(local)

    assert normalised.utcoffset() == timedelta(0)
    assert normalised.hour == 12


def test_isoformat_always_carries_an_offset() -> None:
    value = isoformat(datetime(2026, 7, 9, 12, 30, tzinfo=UTC))
    assert value == "2026-07-09T12:30:00+00:00"


class TestFrozenClock:
    def test_does_not_move_on_its_own(self) -> None:
        clock = FrozenClock(datetime(2026, 7, 9, tzinfo=UTC))
        assert clock.now() == clock.now()

    def test_advance_moves_forward(self) -> None:
        clock = FrozenClock(datetime(2026, 7, 9, tzinfo=UTC))
        start = clock.now()

        clock.advance(90.5)

        assert clock.now() - start == timedelta(seconds=90.5)

    def test_refuses_to_move_backwards(self) -> None:
        """Cooldowns and anchor ages are computed from differences. A clock that
        can go backwards makes those durations negative and the logic unsound."""
        clock = FrozenClock(datetime(2026, 7, 9, tzinfo=UTC))
        with pytest.raises(ValueError, match="cannot move backwards"):
            clock.advance(-1)

    def test_rejects_naive_start(self) -> None:
        with pytest.raises(ValueError, match="naive datetime rejected"):
            FrozenClock(datetime(2026, 7, 9))  # noqa: DTZ001 — the point of the test
