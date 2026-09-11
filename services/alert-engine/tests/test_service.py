"""`alert-engine` lifecycle and health contract.

Redis is critical here, and the asymmetry with `vision-worker` is deliberate:
without the spine there are no triggers to process, so this service has nothing
to degrade to. It withdraws from readiness and its stream position stays
un-acknowledged, so nothing is lost.
"""

from __future__ import annotations

import asyncio
import socket
from collections.abc import Iterator
from unittest.mock import AsyncMock

import pytest

from mansour_alert_engine.service import AlertEngine
from mansour_alert_engine.settings import AlertEngineSettings, get_redis_settings
from mansour_common.health import Status


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


@pytest.fixture
def settings() -> AlertEngineSettings:
    return AlertEngineSettings(
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
    monkeypatch.setattr("mansour_alert_engine.service.EventBus", lambda _settings: bus)
    get_redis_settings.cache_clear()
    yield bus
    get_redis_settings.cache_clear()


class TestHealthContract:
    async def test_redis_is_critical(
        self, settings: AlertEngineSettings, stub_eventbus: AsyncMock
    ) -> None:
        engine = AlertEngine(settings)
        await engine.setup()

        stub_eventbus.ping.side_effect = RuntimeError("connection refused")
        report = await engine.health.check(use_cache=False)

        assert report.status is Status.FAILED
        assert not report.ready

    async def test_ready_when_redis_is_up(
        self, settings: AlertEngineSettings, stub_eventbus: AsyncMock
    ) -> None:
        engine = AlertEngine(settings)
        await engine.setup()

        assert (await engine.health.check(use_cache=False)).status is Status.OK


class TestLifecycle:
    async def test_runs_until_stopped_and_closes_the_eventbus(
        self, settings: AlertEngineSettings, stub_eventbus: AsyncMock
    ) -> None:
        engine = AlertEngine(settings)
        stopping = asyncio.Event()

        task = asyncio.create_task(engine.run(stopping))
        await asyncio.sleep(0.05)
        assert not task.done()

        stopping.set()
        await asyncio.wait_for(task, timeout=5)

        stub_eventbus.close.assert_awaited_once()


class TestSettings:
    def test_cooldown_must_be_positive(self) -> None:
        """A zero cooldown makes a sustained condition emit one alert per tick."""
        with pytest.raises(ValueError, match="default_cooldown_seconds"):
            AlertEngineSettings(default_cooldown_seconds=0)

    def test_escalation_timeout_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="escalation_timeout_seconds"):
            AlertEngineSettings(escalation_timeout_seconds=0)

    def test_defaults_match_the_specification(self, settings: AlertEngineSettings) -> None:
        assert settings.default_cooldown_seconds == 60.0
        assert settings.escalation_timeout_seconds == 120.0
