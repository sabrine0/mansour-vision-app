"""The `analytics-consumer` daemon.

Consumes the tick, crossing, and health streams; writes TimescaleDB aggregates;
reconciles zone occupancy against direct density estimates; derives dwell time by
Little's Law without following any individual (ADR 0006).

Milestone 2 establishes the process. Aggregation is Milestone 4.

Health contract: Redis is critical — without it there is nothing to consume.
PostgreSQL is critical too, because this service's entire output is a write to
it; a consumer that reads the spine and cannot persist is merely destroying
messages. When it is down, this service withdraws from readiness and its stream
position is left un-acknowledged, so the aggregates are backfilled by replay once
the database returns. Volume II §25: a gap that replay fills, never a silent loss.
"""

from __future__ import annotations

import asyncio

from mansour_analytics.settings import AnalyticsSettings, get_redis_settings
from mansour_common.daemon import Daemon
from mansour_common.eventbus import EventBus
from mansour_common.logging import get_logger

log = get_logger(__name__)


class AnalyticsConsumer(Daemon):
    def __init__(self, settings: AnalyticsSettings) -> None:
        super().__init__(settings)
        self.settings: AnalyticsSettings = settings
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
            "analytics.configured",
            consumer_name=self.settings.consumer_name,
            anchor_interval_seconds=self.settings.occupancy_anchor_interval_seconds,
            littles_law_window_seconds=self.settings.littles_law_window_seconds,
        )

    async def work(self, stopping: asyncio.Event) -> None:
        """Idle until stopped. Stream consumption arrives in Milestone 4."""
        await stopping.wait()


__all__ = ["AnalyticsConsumer"]
