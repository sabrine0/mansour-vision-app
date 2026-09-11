"""Redis connection lifecycle.

Redis is the event spine (ADR 0007). `core-api` does not consume from it — the
analytics and alert services do — but it publishes configuration-change
notifications and must be able to report the spine's health.
"""

from __future__ import annotations

from redis.asyncio import ConnectionPool, Redis
from redis.exceptions import RedisError

from mansour_common.config import RedisSettings
from mansour_common.errors import DependencyError


class EventBus:
    """Owns the Redis connection pool for one process."""

    def __init__(self, settings: RedisSettings) -> None:
        self._pool = ConnectionPool.from_url(
            settings.url(),
            max_connections=settings.max_connections,
            socket_timeout=settings.socket_timeout_seconds,
            socket_connect_timeout=settings.socket_connect_timeout_seconds,
            # Without this, a dropped connection is only discovered on the next
            # command, which is the command that then fails.
            health_check_interval=30,
            decode_responses=True,
        )
        self._client: Redis = Redis(connection_pool=self._pool)

    @property
    def client(self) -> Redis:
        return self._client

    async def ping(self) -> None:
        try:
            await self._client.ping()
        except (RedisError, OSError) as exc:
            raise DependencyError("redis unreachable", error=str(exc)) from exc

    async def close(self) -> None:
        await self._client.aclose()
        await self._pool.disconnect()


__all__ = ["EventBus"]
