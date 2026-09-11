"""Configuration for `alert-engine`."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from mansour_common.config import PostgresSettings, RedisSettings, ServiceSettings, load


class AlertEngineSettings(ServiceSettings):
    """Consumes `rule.trigger` and `camera.health`; raises, clusters, and escalates alerts."""

    model_config = SettingsConfigDict(
        env_prefix="ALERT_ENGINE_",
        env_file=".env",
        extra="forbid",
        frozen=True,
    )

    service_name: str = "alert-engine"

    #: Identifies this replica within its consumer group.
    consumer_name: str = Field(default="alert-engine-1", min_length=1, max_length=64)

    #: Minimum seconds between two firings of the same rule for the same scope.
    #: Generalises the prototype's per-object cooldown to a form that survives a
    #: restart, because the dedup key is uniquely indexed in PostgreSQL.
    default_cooldown_seconds: float = Field(default=60.0, gt=0)

    #: Seconds an unacknowledged notification waits before escalating (`NTF-005`).
    #: The failure mode of every alerting system ever built is the alert nobody
    #: saw; the timer is the only defence.
    escalation_timeout_seconds: float = Field(default=120.0, gt=0)

    #: Messages read per XREADGROUP call.
    batch_size: int = Field(default=64, ge=1, le=1000)
    #: Milliseconds to block waiting for new messages.
    block_ms: int = Field(default=2000, ge=100, le=30_000)


@lru_cache(maxsize=1)
def get_settings() -> AlertEngineSettings:
    return load(AlertEngineSettings)


@lru_cache(maxsize=1)
def get_redis_settings() -> RedisSettings:
    return load(RedisSettings)


@lru_cache(maxsize=1)
def get_postgres_settings() -> PostgresSettings:
    return load(PostgresSettings)


__all__ = [
    "AlertEngineSettings",
    "get_postgres_settings",
    "get_redis_settings",
    "get_settings",
]
