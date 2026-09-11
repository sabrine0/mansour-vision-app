"""Configuration for the control plane."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from mansour_common.config import PostgresSettings, RedisSettings, ServiceSettings, load


class ApiSettings(ServiceSettings):
    """`core-api` never touches a video frame; it owns identity and configuration."""

    model_config = SettingsConfigDict(
        env_prefix="API_",
        env_file=".env",
        extra="forbid",
        frozen=True,
    )

    service_name: str = "core-api"

    #: The HTTP API port. Distinct from `health_port`: the orchestrator probes
    #: health on a port that is never exposed through the ingress.
    port: int = Field(default=8000, ge=1, le=65535)
    host: str = "0.0.0.0"  # noqa: S104 — containers must bind all interfaces

    #: Origins permitted by CORS. Empty in production unless explicitly set; a
    #: wildcard on a credentialed API is a vulnerability, not a convenience.
    cors_origins: tuple[str, ...] = ()

    #: Emitted on every response and in the OpenAPI document.
    version: str = "0.1.0"

    #: Seconds a readiness result is cached. See mansour_common.health.
    health_cache_seconds: float = Field(default=2.0, ge=0)


@lru_cache(maxsize=1)
def get_settings() -> ApiSettings:
    return load(ApiSettings)


@lru_cache(maxsize=1)
def get_postgres_settings() -> PostgresSettings:
    return load(PostgresSettings)


@lru_cache(maxsize=1)
def get_redis_settings() -> RedisSettings:
    return load(RedisSettings)


__all__ = ["ApiSettings", "get_postgres_settings", "get_redis_settings", "get_settings"]
