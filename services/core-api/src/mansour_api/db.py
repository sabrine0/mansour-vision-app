"""PostgreSQL access.

The engine is created once per process and disposed on shutdown. Sessions are
per-request and are never shared across an `await` boundary that outlives the
request, because a SQLAlchemy `AsyncSession` is not concurrency-safe.

There is no ORM model here. Milestone 3 owns the schema; this module owns the
connection lifecycle, which the health probe needs today.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from mansour_common.config import PostgresSettings
from mansour_common.errors import DependencyError


class Database:
    """Owns the async engine and session factory for one process."""

    def __init__(self, settings: PostgresSettings) -> None:
        self._engine: AsyncEngine = create_async_engine(
            settings.dsn(),
            pool_size=settings.pool_size,
            max_overflow=settings.max_overflow,
            pool_timeout=settings.pool_timeout,
            pool_recycle=settings.pool_recycle_seconds,
            # Verify a pooled connection before handing it out. Without this, the
            # first request after a database restart fails with a stale socket.
            pool_pre_ping=True,
            connect_args={"timeout": settings.connect_timeout_seconds},
            echo=False,
        )
        self._sessionmaker = async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            autoflush=False,
        )

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    async def session(self) -> AsyncIterator[AsyncSession]:
        """FastAPI dependency: one session per request, rolled back on error."""
        async with self._sessionmaker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    async def ping(self) -> None:
        """Health probe. Raises `DependencyError` when PostgreSQL is unreachable."""
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            raise DependencyError("postgres unreachable", error=str(exc)) from exc

    async def close(self) -> None:
        await self._engine.dispose()


__all__ = ["Database"]
