"""`analytics-consumer` lifecycle, health contract, and ADR 0006 parameters."""

from __future__ import annotations

import asyncio
import socket
from collections.abc import Iterator
from unittest.mock import AsyncMock

import pytest

from mansour_analytics.service import AnalyticsConsumer
from mansour_analytics.settings import AnalyticsSettings, get_redis_settings
from mansour_common.health import Status


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


@pytest.fixture
def settings() -> AnalyticsSettings:
    return AnalyticsSettings(
        environment="test",
        log_level="CRITICAL",
        log_render="console",
        health_host="127.0.0.1",
        health_port=_free_port(),
    )


@pytest.fixture
def stub_eventbus(monkeypatch: pytest.MonkeyPatch) -> Iterator[AsyncMock]:
    bus = AsyncMock()
    bus.ping = AsyncMock(return_value=None)
    bus.close = AsyncMock(return_value=None)
    monkeypatch.setattr("mansour_analytics.service.EventBus", lambda _settings: bus)
    get_redis_settings.cache_clear()
    yield bus
    get_redis_settings.cache_clear()


class TestHealthContract:
    async def test_redis_is_critical(
        self, settings: AnalyticsSettings, stub_eventbus: AsyncMock
    ) -> None:
        """A consumer that reads the spine and cannot persist is destroying messages."""
        consumer = AnalyticsConsumer(settings)
        await consumer.setup()

        stub_eventbus.ping.side_effect = RuntimeError("connection refused")
        report = await consumer.health.check(use_cache=False)

        assert report.status is Status.FAILED
        assert not report.ready


class TestLifecycle:
    async def test_runs_until_stopped_and_closes_the_eventbus(
        self, settings: AnalyticsSettings, stub_eventbus: AsyncMock
    ) -> None:
        consumer = AnalyticsConsumer(settings)
        stopping = asyncio.Event()

        task = asyncio.create_task(consumer.run(stopping))
        await asyncio.sleep(0.05)
        assert not task.done()

        stopping.set()
        await asyncio.wait_for(task, timeout=5)

        stub_eventbus.close.assert_awaited_once()


class TestReconciliationParameters:
    def test_occupancy_must_be_re_anchored_periodically(self) -> None:
        """Occupancy from net crossings is an unbounded integrator of error. An
        anchor interval of zero or less would disable reconciliation (ADR 0006)."""
        with pytest.raises(ValueError, match="occupancy_anchor_interval_seconds"):
            AnalyticsSettings(occupancy_anchor_interval_seconds=0)

    def test_littles_law_window_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="littles_law_window_seconds"):
            AnalyticsSettings(littles_law_window_seconds=0)

    def test_dwell_time_suppression_threshold_must_be_positive(self) -> None:
        """W = L / λ diverges as λ approaches zero. Below the threshold the metric
        is suppressed and rendered '—', never as a confident wrong number."""
        with pytest.raises(ValueError, match="littles_law_min_arrival_rate_per_min"):
            AnalyticsSettings(littles_law_min_arrival_rate_per_min=0)

    def test_defaults_match_the_specification(self, settings: AnalyticsSettings) -> None:
        assert settings.littles_law_window_seconds == 600.0
        assert settings.occupancy_anchor_interval_seconds == 300.0
