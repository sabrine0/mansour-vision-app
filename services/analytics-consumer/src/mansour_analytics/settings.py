"""Configuration for `analytics-consumer`."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from mansour_common.config import PostgresSettings, RedisSettings, ServiceSettings, load


class AnalyticsSettings(ServiceSettings):
    """Aggregation, occupancy reconciliation, and dwell time (ADR 0006)."""

    model_config = SettingsConfigDict(
        env_prefix="ANALYTICS_",
        env_file=".env",
        extra="forbid",
        frozen=True,
    )

    service_name: str = "analytics-consumer"

    consumer_name: str = Field(default="analytics-1", min_length=1, max_length=64)

    batch_size: int = Field(default=256, ge=1, le=5000)
    block_ms: int = Field(default=2000, ge=100, le=30_000)

    #: Seconds between re-anchoring a zone's occupancy to a direct density
    #: estimate. Between anchors, occupancy advances by net line crossings and
    #: drifts; without re-anchoring it becomes fiction by hour six (ADR 0006).
    occupancy_anchor_interval_seconds: float = Field(default=300.0, gt=0)

    #: Sliding window over which Little's Law computes mean waiting time.
    #: `W = L / λ` needs approximate steady state; too short a window is noise,
    #: too long a window lags the queue it is describing.
    littles_law_window_seconds: float = Field(default=600.0, gt=0)

    #: Below this arrival rate the dwell-time metric is suppressed and rendered
    #: as "—". A confident wrong number is worse than an absent one.
    littles_law_min_arrival_rate_per_min: float = Field(default=0.5, gt=0)


@lru_cache(maxsize=1)
def get_settings() -> AnalyticsSettings:
    return load(AnalyticsSettings)


@lru_cache(maxsize=1)
def get_redis_settings() -> RedisSettings:
    return load(RedisSettings)


@lru_cache(maxsize=1)
def get_postgres_settings() -> PostgresSettings:
    return load(PostgresSettings)


__all__ = [
    "AnalyticsSettings",
    "get_postgres_settings",
    "get_redis_settings",
    "get_settings",
]
