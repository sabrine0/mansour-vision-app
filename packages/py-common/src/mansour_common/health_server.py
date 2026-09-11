"""A minimal health endpoint for the daemon services.

`core-api` is a FastAPI application and mounts its own health routes. The
workers are not web servers, but the orchestrator still needs to probe them, so
they run this alongside their work loop.

Deliberately Starlette rather than FastAPI: these endpoints have no request body,
no OpenAPI surface, and no authentication, and a worker should not carry a web
framework it does not otherwise use.
"""

from __future__ import annotations

import asyncio
import contextlib

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from mansour_common.health import HealthRegistry


def build_health_app(registry: HealthRegistry, *, service: str, version: str) -> Starlette:
    async def healthz(_: Request) -> JSONResponse:
        """Liveness: the process responds. Deliberately probes nothing external."""
        return JSONResponse({"status": "ok", "service": service, "version": version})

    async def readyz(_: Request) -> JSONResponse:
        report = await registry.check()
        # 503 withdraws the replica from load balancing. A degraded service is
        # still ready — see mansour_common.health.
        return JSONResponse(report.as_dict(), status_code=200 if report.ready else 503)

    return Starlette(
        routes=[
            Route("/healthz", healthz, methods=["GET"]),
            Route("/readyz", readyz, methods=["GET"]),
        ]
    )


class HealthServer:
    """Runs the health app on a background task for the lifetime of a worker."""

    def __init__(
        self,
        registry: HealthRegistry,
        *,
        service: str,
        version: str,
        host: str,
        port: int,
    ) -> None:
        config = uvicorn.Config(
            build_health_app(registry, service=service, version=version),
            host=host,
            port=port,
            log_config=None,  # structlog owns logging
            access_log=False,
            lifespan="off",
        )
        self._server = uvicorn.Server(config)
        self._task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> HealthServer:
        self._task = asyncio.create_task(self._server.serve(), name="health-server")
        return self

    async def __aexit__(self, *_exc: object) -> None:
        self._server.should_exit = True
        if self._task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await self._task


__all__ = ["HealthServer", "build_health_app"]
