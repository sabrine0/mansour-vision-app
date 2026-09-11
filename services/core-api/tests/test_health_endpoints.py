"""Liveness must not depend on anything. Readiness must depend on the right things."""

from __future__ import annotations

from fastapi import FastAPI
from httpx import AsyncClient

from mansour_common.health import HealthRegistry


async def _fail() -> None:
    raise RuntimeError("connection refused")


class TestLiveness:
    async def test_returns_ok(self, client: AsyncClient) -> None:
        response = await client.get("/healthz")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["service"] == "core-api"

    async def test_stays_ok_when_every_dependency_is_down(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        """A database outage that fails liveness gets every replica killed,
        turning a recoverable failure into a total one."""
        registry = HealthRegistry(cache_seconds=0)
        registry.register("postgres", _fail, critical=True)
        registry.register("redis", _fail, critical=True)
        app.state.resources.health = registry

        assert (await client.get("/healthz")).status_code == 200


class TestReadiness:
    async def test_ready_when_dependencies_are_up(self, client: AsyncClient) -> None:
        response = await client.get("/readyz")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["checks"]["postgres"]["status"] == "ok"
        assert body["checks"]["redis"]["status"] == "ok"

    async def test_not_ready_when_a_critical_dependency_is_down(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        registry = HealthRegistry(cache_seconds=0)
        registry.register("postgres", _fail, critical=True)
        app.state.resources.health = registry

        response = await client.get("/readyz")

        assert response.status_code == 503
        assert response.json()["status"] == "failed"

    async def test_degraded_when_a_non_critical_dependency_is_down(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        registry = HealthRegistry(cache_seconds=0)
        registry.register("postgres", _ok_probe, critical=True)
        registry.register("metrics", _fail, critical=False)
        app.state.resources.health = registry

        response = await client.get("/readyz")

        assert response.status_code == 200, "a degraded service must remain in rotation"
        assert response.json()["status"] == "degraded"

    async def test_failure_detail_is_reported(self, app: FastAPI, client: AsyncClient) -> None:
        registry = HealthRegistry(cache_seconds=0)
        registry.register("redis", _fail, critical=True)
        app.state.resources.health = registry

        body = (await client.get("/readyz")).json()

        assert body["checks"]["redis"]["detail"] == "connection refused"


async def _ok_probe() -> None:
    return None
