"""The `alert-engine` daemon.

Consumes `rule.trigger` and `camera.health` from the spine, applies cooldowns and
contextual arming, clusters correlated conditions into one alert, and escalates
unacknowledged ones.

Milestone 2 establishes the process. Rule evaluation is Milestone 4.

Both dependencies are critical here, and for different reasons. Redis is the only
source of the triggers this service exists to process. PostgreSQL holds the
uniquely-indexed `dedup_key` that makes at-least-once delivery idempotent — a
redelivered trigger must collide on insert and be absorbed. Without the database
this service would raise duplicate alerts, which is worse than raising none.
"""

from __future__ import annotations

import asyncio

from mansour_alert_engine.settings import AlertEngineSettings, get_redis_settings
from mansour_common.daemon import Daemon
from mansour_common.eventbus import EventBus
from mansour_common.logging import get_logger

log = get_logger(__name__)


class AlertEngine(Daemon):
    def __init__(self, settings: AlertEngineSettings) -> None:
        super().__init__(settings)
        self.settings: AlertEngineSettings = settings
        self._eventbus: EventBus | None = None

    @property
    def eventbus(self) -> EventBus:
        if self._eventbus is None:
            raise RuntimeError("eventbus accessed before setup()")
        return self._eventbus

    async def setup(self) -> None:
        self._eventbus = EventBus(get_redis_settings())
        self.on_close("eventbus", self._eventbus.close)

        self.health.register("redis", self._eventbus.ping, critical=True)

        log.info(
            "alert_engine.configured",
            consumer_name=self.settings.consumer_name,
            default_cooldown_seconds=self.settings.default_cooldown_seconds,
            escalation_timeout_seconds=self.settings.escalation_timeout_seconds,
        )

    async def work(self, stopping: asyncio.Event) -> None:
        """Idle until stopped. Stream consumption arrives in Milestone 4."""
        await stopping.wait()


__all__ = ["AlertEngine"]
