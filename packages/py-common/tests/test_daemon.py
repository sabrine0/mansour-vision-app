"""Daemon lifecycle: setup, serve health, drain, dispose in reverse order."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from mansour_common.config import ServiceSettings
from mansour_common.daemon import Daemon
from mansour_common.health_server import build_health_app


def _free_port() -> int:
    """Claim an ephemeral port and release it.

    `health_port=0` is rejected by `ServiceSettings`, and rightly so: zero is not
    a port an operator can configure. Tests must therefore find a real one.
    """
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


def _settings(**overrides: object) -> ServiceSettings:
    base: dict[str, object] = {
        "service_name": "test-daemon",
        "environment": "test",
        "log_level": "CRITICAL",
        "log_render": "console",
        "health_host": "127.0.0.1",
        "health_port": _free_port(),
    }
    base.update(overrides)
    return ServiceSettings(**base)  # type: ignore[arg-type]


class _Recorder(Daemon):
    def __init__(self) -> None:
        super().__init__(_settings())
        self.events: list[str] = []

    async def setup(self) -> None:
        self.events.append("setup")
        self.on_close("first", self._close_first)
        self.on_close("second", self._close_second)

    async def work(self, stopping: asyncio.Event) -> None:
        self.events.append("work")
        await stopping.wait()
        self.events.append("drained")

    async def _close_first(self) -> None:
        self.events.append("close:first")

    async def _close_second(self) -> None:
        self.events.append("close:second")


class _FailingCloser(Daemon):
    def __init__(self) -> None:
        super().__init__(_settings())
        self.closed: list[str] = []

    async def setup(self) -> None:
        self.on_close("good", self._good)
        self.on_close("bad", self._bad)

    async def work(self, stopping: asyncio.Event) -> None:
        return None

    async def _good(self) -> None:
        self.closed.append("good")

    async def _bad(self) -> None:
        raise RuntimeError("pool would not close")


async def _run_briefly(daemon: Daemon, *, hold: float = 0.05) -> None:
    stopping = asyncio.Event()
    task = asyncio.create_task(daemon.run(stopping))
    await asyncio.sleep(hold)
    stopping.set()
    await asyncio.wait_for(task, timeout=5)


async def test_setup_runs_before_work_and_closers_run_last() -> None:
    daemon = _Recorder()

    await _run_briefly(daemon)

    assert daemon.events == ["setup", "work", "drained", "close:second", "close:first"]


async def test_closers_run_in_reverse_registration_order() -> None:
    """Dependencies are acquired in order and must be released in the reverse."""
    daemon = _Recorder()

    await _run_briefly(daemon)

    assert daemon.events.index("close:second") < daemon.events.index("close:first")


async def test_a_failing_closer_does_not_prevent_the_others() -> None:
    daemon = _FailingCloser()

    await _run_briefly(daemon, hold=0.01)

    assert daemon.closed == ["good"], "the good closer must still run"


async def test_default_work_idles_until_stopped() -> None:
    """A service whose domain logic is not yet implemented still starts, reports
    health, and shuts down cleanly. It does not pretend to do work."""
    daemon = Daemon(_settings())

    stopping = asyncio.Event()
    task = asyncio.create_task(daemon.run(stopping))
    await asyncio.sleep(0.05)

    assert not task.done(), "the daemon must not exit on its own"

    stopping.set()
    await asyncio.wait_for(task, timeout=5)


async def test_close_is_idempotent() -> None:
    daemon = _Recorder()
    await _run_briefly(daemon)
    before = list(daemon.events)

    await daemon.close()

    assert daemon.events == before, "closers must not run twice"


class TestHealthApp:
    @pytest.fixture
    def registry_app(self) -> httpx.ASGITransport:
        from mansour_common.health import HealthRegistry

        registry = HealthRegistry(cache_seconds=0)
        registry.register("redis", _ok, critical=True)
        app = build_health_app(registry, service="test-daemon", version="9.9.9")
        return httpx.ASGITransport(app=app)

    async def test_healthz_reports_service_identity(
        self, registry_app: httpx.ASGITransport
    ) -> None:
        async with httpx.AsyncClient(transport=registry_app, base_url="http://t") as client:
            body = (await client.get("/healthz")).json()

        assert body == {"status": "ok", "service": "test-daemon", "version": "9.9.9"}

    async def test_readyz_reports_checks(self, registry_app: httpx.ASGITransport) -> None:
        async with httpx.AsyncClient(transport=registry_app, base_url="http://t") as client:
            response = await client.get("/readyz")

        assert response.status_code == 200
        assert response.json()["checks"]["redis"]["status"] == "ok"

    async def test_readyz_returns_503_when_a_critical_check_fails(self) -> None:
        from mansour_common.health import HealthRegistry

        registry = HealthRegistry(cache_seconds=0)
        registry.register("redis", _fail, critical=True)
        transport = httpx.ASGITransport(app=build_health_app(registry, service="d", version="1"))

        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            assert (await client.get("/readyz")).status_code == 503


async def _ok() -> None:
    return None


async def _fail() -> None:
    raise RuntimeError("connection refused")
