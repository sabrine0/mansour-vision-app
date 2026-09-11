"""`vision-worker` lifecycle and, most importantly, its health contract.

Volume II §25 says a spine outage must degrade the worker, not stop it: detection
is the one thing that must never stop. That is expressed as `critical=False` on
the Redis check, and it is the single most consequential line in this service.
"""

from __future__ import annotations

import asyncio
import socket
from collections.abc import Iterator
from unittest.mock import AsyncMock

import pytest

from mansour_common.health import Status
from mansour_vision_worker.service import VisionWorker
from mansour_vision_worker.settings import WorkerSettings, get_redis_settings


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


@pytest.fixture
def settings() -> WorkerSettings:
    return WorkerSettings(
        environment="test",
        log_level="CRITICAL",
        log_render="console",
        health_host="127.0.0.1",
        health_port=_free_port(),
        worker_id="worker-test",
    )


@pytest.fixture
def stub_eventbus(monkeypatch: pytest.MonkeyPatch) -> Iterator[AsyncMock]:
    """Replace the Redis client. These tests are about the worker, not Redis."""
    bus = AsyncMock()
    bus.ping = AsyncMock(return_value=None)
    bus.close = AsyncMock(return_value=None)
    monkeypatch.setattr("mansour_vision_worker.service.EventBus", lambda _settings: bus)
    get_redis_settings.cache_clear()
    yield bus
    get_redis_settings.cache_clear()


class TestHealthContract:
    async def test_redis_is_not_critical(
        self, settings: WorkerSettings, stub_eventbus: AsyncMock
    ) -> None:
        """A spine outage must not take the worker's cameras offline."""
        worker = VisionWorker(settings)
        await worker.setup()

        stub_eventbus.ping.side_effect = RuntimeError("connection refused")
        report = await worker.health.check(use_cache=False)

        assert report.status is Status.DEGRADED
        assert report.ready, "the worker keeps detecting through a spine outage"

    async def test_healthy_when_redis_is_up(
        self, settings: WorkerSettings, stub_eventbus: AsyncMock
    ) -> None:
        worker = VisionWorker(settings)
        await worker.setup()

        report = await worker.health.check(use_cache=False)

        assert report.status is Status.OK

    async def test_postgres_is_not_a_dependency_at_all(
        self, settings: WorkerSettings, stub_eventbus: AsyncMock
    ) -> None:
        """The worker never writes to the database. A slow DB cannot stall detection."""
        worker = VisionWorker(settings)
        await worker.setup()

        report = await worker.health.check(use_cache=False)

        assert {c.name for c in report.checks} == {"redis"}


class TestLifecycle:
    async def test_runs_until_stopped_and_closes_the_eventbus(
        self, settings: WorkerSettings, stub_eventbus: AsyncMock
    ) -> None:
        worker = VisionWorker(settings)
        stopping = asyncio.Event()

        task = asyncio.create_task(worker.run(stopping))
        await asyncio.sleep(0.05)
        assert not task.done(), "the worker must not exit on its own"

        stopping.set()
        await asyncio.wait_for(task, timeout=5)

        stub_eventbus.close.assert_awaited_once()

    async def test_eventbus_access_before_setup_is_an_error(self, settings: WorkerSettings) -> None:
        with pytest.raises(RuntimeError, match="before setup"):
            _ = VisionWorker(settings).eventbus


class TestSettings:
    def test_analytic_fps_is_bounded(self) -> None:
        with pytest.raises(ValueError, match="analytic_fps"):
            WorkerSettings(analytic_fps=0)

    def test_producer_identity_is_required(self) -> None:
        with pytest.raises(ValueError, match="worker_id"):
            WorkerSettings(worker_id="")

    def test_priority_cameras_default_to_none(self, settings: WorkerSettings) -> None:
        assert settings.priority_camera_ids == ()

    def test_offline_detection_is_keyed_on_a_positive_staleness_window(self) -> None:
        with pytest.raises(ValueError, match="camera_offline_after_seconds"):
            WorkerSettings(camera_offline_after_seconds=0)
