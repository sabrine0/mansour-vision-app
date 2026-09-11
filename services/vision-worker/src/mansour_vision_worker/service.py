"""The `vision-worker` daemon.

Owns cameras. Decodes, detects, tracks, evaluates zone and line geometry, and
publishes **already-aggregated** events onto the spine — never a per-object
detection (ADR 0007).

Milestone 2 establishes the process: configuration, the Redis connection, health,
and graceful shutdown. The capture and inference pipeline is Milestone 3, gated on
the benchmark harness fixing the execution provider (ADR 0005).

The health contract is the interesting part today, and it is deliberate:
PostgreSQL is **not** a dependency of this service at all, and Redis is
**non-critical**. Volume II §25 requires that a spine outage degrade the worker
rather than stop it — the worker buffers locally and keeps detecting, because
detection is the one thing that must never stop. Withdrawing the worker from
service when Redis blinks would take its cameras offline for no reason.
"""

from __future__ import annotations

import asyncio

from mansour_common.daemon import Daemon
from mansour_common.eventbus import EventBus
from mansour_common.logging import get_logger
from mansour_vision_worker.settings import WorkerSettings, get_redis_settings

log = get_logger(__name__)


class VisionWorker(Daemon):
    def __init__(self, settings: WorkerSettings) -> None:
        super().__init__(settings)
        self.settings: WorkerSettings = settings
        self._eventbus: EventBus | None = None

    @property
    def eventbus(self) -> EventBus:
        if self._eventbus is None:
            raise RuntimeError("eventbus accessed before setup()")
        return self._eventbus

    async def setup(self) -> None:
        self._eventbus = EventBus(get_redis_settings())
        self.on_close("eventbus", self._eventbus.close)

        # Non-critical: the worker keeps detecting through a spine outage.
        self.health.register("redis", self._eventbus.ping, critical=False)

        log.info(
            "worker.configured",
            worker_id=self.settings.worker_id,
            analytic_fps=self.settings.analytic_fps,
            execution_provider=self.settings.execution_provider,
            priority_cameras=len(self.settings.priority_camera_ids),
        )

    async def work(self, stopping: asyncio.Event) -> None:
        """Idle until stopped.

        No camera is opened and no model is loaded in Milestone 2. The worker
        reports its health truthfully — including that it is analysing nothing —
        rather than simulating a pipeline it does not have.
        """
        await stopping.wait()


__all__ = ["VisionWorker"]
