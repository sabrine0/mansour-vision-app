"""The `core-api` ASGI application.

Owns identity, authorization, configuration, and audit. It never opens a camera,
never decodes a frame, and never runs a model. That separation is what lets the
API be restarted during an event without interrupting detection (ADR 0007,
Operational SRS §25).

Milestone 2 ships the application shell: configuration, logging, middleware,
dependency lifecycle, and health. Domain routers arrive in Milestone 3.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mansour_api.db import Database
from mansour_api.middleware import (
    AccessLogMiddleware,
    CorrelationIdMiddleware,
    ErrorHandlingMiddleware,
)
from mansour_api.routers import health as health_router
from mansour_api.settings import (
    ApiSettings,
    get_postgres_settings,
    get_redis_settings,
    get_settings,
)
from mansour_common.eventbus import EventBus
from mansour_common.health import HealthRegistry
from mansour_common.logging import configure_logging, get_logger

log = get_logger(__name__)


@dataclass(slots=True)
class Resources:
    """Process-lifetime dependencies, created on startup and disposed on shutdown."""

    database: Database
    eventbus: EventBus
    health: HealthRegistry


def _build_resources(settings: ApiSettings) -> Resources:
    database = Database(get_postgres_settings())
    eventbus = EventBus(get_redis_settings())
    health = HealthRegistry(cache_seconds=settings.health_cache_seconds)

    # `core-api` cannot serve its purpose without PostgreSQL: it is the system of
    # record for identity and configuration. Redis is likewise critical here,
    # because configuration changes must reach the workers (`CFG-005`).
    health.register("postgres", database.ping, critical=True)
    health.register("redis", eventbus.ping, critical=True)

    return Resources(database=database, eventbus=eventbus, health=health)


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    """Application factory. Tests construct their own instance; they never import a global."""
    settings = settings or get_settings()
    configure_logging(
        service=settings.service_name,
        level=settings.log_level,
        render=settings.log_render,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resources = _build_resources(settings)
        app.state.resources = resources
        app.state.settings = settings
        log.info(
            "service.started",
            version=settings.version,
            environment=settings.environment,
            port=settings.port,
        )
        try:
            yield
        finally:
            # Dispose in reverse order of creation. Failure to close one
            # dependency must not prevent the others from closing.
            for name, close in (
                ("redis", resources.eventbus.close),
                ("postgres", resources.database.close),
            ):
                try:
                    await close()
                except Exception:
                    log.exception("service.shutdown_failed", dependency=name)
            log.info("service.stopped")

    app = FastAPI(
        title="MANSOUR Vision — Core API",
        version=settings.version,
        description=(
            "Control plane for the MANSOUR Vision Event Command & Control Platform. "
            "Performs anonymous operational monitoring only: no face recognition, "
            "no person identification, no biometric categorisation, no re-identification, "
            "no licence plate recognition. See docs/adr/0004-no-biometric-inference.md."
        ),
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    # Middleware executes bottom-up on the request path. Error handling is added
    # last so it wraps everything, and the correlation id is bound before any
    # handler can log.
    app.add_middleware(ErrorHandlingMiddleware, debug=not settings.is_production)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(CorrelationIdMiddleware)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        )

    app.include_router(health_router.router)
    return app


__all__ = ["Resources", "create_app"]
