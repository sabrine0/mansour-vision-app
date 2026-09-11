"""Liveness and readiness endpoints.

`/healthz` deliberately probes nothing. A database outage that fails liveness
gets every replica killed by the orchestrator, converting a recoverable
dependency failure into a total one.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response, status

from mansour_common.health import ReadinessReport

router = APIRouter(tags=["health"])


@router.get("/healthz", summary="Liveness probe")
async def healthz(request: Request) -> dict[str, Any]:
    """The process is alive and the event loop is turning."""
    settings = request.app.state.settings
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.version,
    }


@router.get("/readyz", summary="Readiness probe")
async def readyz(request: Request, response: Response) -> dict[str, Any]:
    """Dependencies are reachable and this replica should receive traffic.

    A degraded service (a non-critical dependency is down) remains ready and says
    plainly what it no longer knows. Only a failed critical check returns 503,
    which withdraws the replica from load balancing.
    """
    # `app.state` is untyped by Starlette; anchor the type here rather than
    # letting `Any` leak into the response contract.
    report: ReadinessReport = await request.app.state.resources.health.check()
    if not report.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return report.as_dict()


__all__ = ["router"]
