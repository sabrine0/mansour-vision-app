"""Test fixtures for `core-api`.

These tests exercise the application shell without PostgreSQL or Redis. The real
dependencies are covered by integration tests (marked `integration`) that run
against the Compose stack; what is under test here is the shell's behaviour when
those dependencies succeed, fail, or hang — which is precisely the behaviour that
is hardest to reproduce with the real thing.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from mansour_api.app import create_app
from mansour_api.settings import ApiSettings
from mansour_common.health import HealthRegistry


@pytest.fixture
def settings() -> ApiSettings:
    return ApiSettings(environment="test", log_render="console", log_level="WARNING")


async def _ok() -> None:
    return None


@pytest.fixture
def health_registry() -> HealthRegistry:
    """A registry whose checks pass. Individual tests re-register failing ones."""
    registry = HealthRegistry(cache_seconds=0)
    registry.register("postgres", _ok, critical=True)
    registry.register("redis", _ok, critical=True)
    return registry


@pytest.fixture
def app(settings: ApiSettings, health_registry: HealthRegistry) -> FastAPI:
    """The real application, with its dependency lifecycle short-circuited.

    `create_app`'s lifespan opens genuine connection pools. `httpx.ASGITransport`
    does not run lifespan, so state is injected here instead. The middleware
    stack, routers, and exception handling under test are the production ones.
    """
    application = create_app(settings)
    application.state.settings = settings
    application.state.resources = _StubResources(health_registry)
    return application


class _StubResources:
    __slots__ = ("health",)

    def __init__(self, health: HealthRegistry) -> None:
        self.health = health


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http


@pytest.fixture
def add_route(app: FastAPI) -> Callable[[str, Callable[[], Any]], None]:
    """Attach a route to the app under test, so middleware can be exercised."""

    def _add(path: str, handler: Callable[[], Any]) -> None:
        app.add_api_route(path, handler, methods=["GET"])

    return _add
