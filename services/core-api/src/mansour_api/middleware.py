"""Request-scoped cross-cutting concerns.

Every request gets a correlation id, either the caller's `X-Request-ID` or a
fresh one, bound to the logging context for the duration. That is how one
incident's trail is reconstructed across `core-api`, the workers, and the alert
engine.

Unhandled exceptions are converted to a stable error envelope. A traceback must
never reach a client: it names internal paths, library versions, and occasionally
a connection string.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from mansour_common.errors import (
    ConfigurationError,
    ConflictError,
    DependencyError,
    MansourError,
    ValidationError,
)
from mansour_common.ids import correlation_id as new_correlation_id
from mansour_common.logging import get_logger, set_correlation_id

log = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"

#: How each deliberate error surfaces to a client.
_STATUS_BY_ERROR: dict[type[MansourError], int] = {
    ValidationError: 400,
    ConflictError: 409,
    DependencyError: 503,
    ConfigurationError: 500,
}

#: Paths excluded from access logging. Orchestrator probes run every few seconds
#: and would otherwise drown the log in noise that carries no information.
_QUIET_PATHS = frozenset({"/healthz", "/readyz"})


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Bind a correlation id for the lifetime of the request, and echo it back."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        cid = request.headers.get(REQUEST_ID_HEADER) or new_correlation_id()
        set_correlation_id(cid)
        request.state.correlation_id = cid
        try:
            response = await call_next(request)
        finally:
            # The contextvar is per-task, but an explicit reset keeps a pooled
            # worker thread from leaking one request's id into the next.
            set_correlation_id(None)
        response.headers[REQUEST_ID_HEADER] = cid
        return response


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Structured access logging with request duration."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000

        if request.url.path not in _QUIET_PATHS:
            log.info(
                "http.request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=round(elapsed_ms, 2),
            )
        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Convert exceptions into a stable envelope. Never leak a traceback."""

    def __init__(self, app: ASGIApp, *, debug: bool = False) -> None:
        super().__init__(app)
        self._debug = debug

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        try:
            return await call_next(request)
        except MansourError as exc:
            status = _status_for(exc)
            log.warning(
                "http.error",
                code=exc.code,
                status=status,
                path=request.url.path,
                retryable=exc.retryable,
                **exc.context,
            )
            return _error_response(status, exc.code, exc.message, retryable=exc.retryable)
        except Exception as exc:
            log.exception("http.unhandled", path=request.url.path)
            message = str(exc) if self._debug else "internal server error"
            return _error_response(500, "internal_error", message, retryable=False)


def _status_for(exc: MansourError) -> int:
    for error_type, status in _STATUS_BY_ERROR.items():
        if isinstance(exc, error_type):
            return status
    return 500


def _error_response(status: int, code: str, message: str, *, retryable: bool) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "retryable": retryable}},
    )


__all__ = [
    "REQUEST_ID_HEADER",
    "AccessLogMiddleware",
    "CorrelationIdMiddleware",
    "ErrorHandlingMiddleware",
]
