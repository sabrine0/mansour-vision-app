"""The shape of a non-HTTP service.

`vision-worker`, `alert-engine` and `analytics-consumer` are daemons. They all
need the same frame: dependency lifecycle, a health endpoint the orchestrator can
probe, structured logging, and a graceful drain on SIGTERM. Only `work()` differs.

Subclasses override `work()`. The default implementation idles until asked to
stop, which is the honest behaviour of a service that has been initialised but
whose domain logic is not yet implemented — it starts, reports its health
truthfully, and shuts down cleanly.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from mansour_common.config import ServiceSettings
from mansour_common.health import HealthRegistry
from mansour_common.health_server import HealthServer
from mansour_common.logging import configure_logging, get_logger

log = get_logger(__name__)

#: An async callable to invoke when the daemon shuts down (close a pool, etc).
Closer = Callable[[], Awaitable[None]]


class Daemon:
    """Base class for the long-running services."""

    def __init__(self, settings: ServiceSettings, *, version: str = "0.1.0") -> None:
        self.settings = settings
        self.version = version
        self.health = HealthRegistry()
        self._closers: list[tuple[str, Closer]] = []
        configure_logging(
            service=settings.service_name,
            level=settings.log_level,
            render=settings.log_render,
        )

    # ---- lifecycle hooks -------------------------------------------------

    async def setup(self) -> None:
        """Acquire dependencies and register health checks. Override in a subclass."""

    async def work(self, stopping: asyncio.Event) -> None:
        """The service body. Must return promptly once `stopping` is set."""
        await stopping.wait()

    def on_close(self, name: str, closer: Closer) -> None:
        """Register a resource to dispose on shutdown, in reverse registration order."""
        self._closers.append((name, closer))

    # ---- driven by mansour_common.lifecycle.run_service -------------------

    async def run(self, stopping: asyncio.Event) -> None:
        await self.setup()
        server = HealthServer(
            self.health,
            service=self.settings.service_name,
            version=self.version,
            host=self.settings.health_host,
            port=self.settings.health_port,
        )
        log.info(
            "service.started",
            version=self.version,
            environment=self.settings.environment,
            health_port=self.settings.health_port,
        )
        try:
            async with server:
                await self.work(stopping)
        finally:
            await self.close()
            log.info("service.stopped")

    async def close(self) -> None:
        """Dispose registered resources. One failure must not block the others."""
        for name, closer in reversed(self._closers):
            try:
                await closer()
            except Exception:
                log.exception("service.close_failed", resource=name)
        self._closers.clear()


__all__ = ["Closer", "Daemon"]
