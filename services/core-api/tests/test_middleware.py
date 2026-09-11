"""Correlation, access logging, and the error boundary.

A traceback must never reach a client: it names internal paths, library versions,
and occasionally a connection string.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from mansour_api.app import create_app
from mansour_api.middleware import REQUEST_ID_HEADER
from mansour_api.settings import ApiSettings
from mansour_common.errors import ConflictError, DependencyError, ValidationError
from mansour_common.logging import get_correlation_id


class TestCorrelationId:
    async def test_generated_when_absent(self, client: AsyncClient) -> None:
        response = await client.get("/healthz")

        cid = response.headers[REQUEST_ID_HEADER]
        assert len(cid) == 32

    async def test_callers_id_is_honoured_and_echoed(self, client: AsyncClient) -> None:
        response = await client.get("/healthz", headers={REQUEST_ID_HEADER: "trace-abc"})

        assert response.headers[REQUEST_ID_HEADER] == "trace-abc"

    async def test_is_bound_during_the_request(
        self, add_route: Callable[[str, Callable[[], Any]], None], client: AsyncClient
    ) -> None:
        seen: list[str | None] = []

        async def handler() -> dict[str, str]:
            seen.append(get_correlation_id())
            return {"ok": "true"}

        add_route("/echo-cid", handler)
        await client.get("/echo-cid", headers={REQUEST_ID_HEADER: "trace-xyz"})

        assert seen == ["trace-xyz"]

    async def test_is_cleared_after_the_request(self, client: AsyncClient) -> None:
        await client.get("/healthz", headers={REQUEST_ID_HEADER: "trace-abc"})
        assert get_correlation_id() is None

    async def test_ids_do_not_leak_between_requests(
        self, add_route: Callable[[str, Callable[[], Any]], None], client: AsyncClient
    ) -> None:
        seen: list[str | None] = []

        async def handler() -> dict[str, str]:
            seen.append(get_correlation_id())
            return {"ok": "true"}

        add_route("/echo-cid", handler)
        await client.get("/echo-cid", headers={REQUEST_ID_HEADER: "first"})
        await client.get("/echo-cid", headers={REQUEST_ID_HEADER: "second"})

        assert seen == ["first", "second"]


class TestErrorBoundary:
    @pytest.mark.parametrize(
        ("exc", "expected_status", "expected_code", "retryable"),
        [
            (ValidationError("bad polygon"), 400, "validation_error", False),
            (ConflictError("already acknowledged"), 409, "conflict", False),
            (DependencyError("postgres unreachable"), 503, "dependency_unavailable", True),
        ],
    )
    async def test_deliberate_errors_map_to_a_stable_envelope(
        self,
        add_route: Callable[[str, Callable[[], Any]], None],
        client: AsyncClient,
        exc: Exception,
        expected_status: int,
        expected_code: str,
        retryable: bool,
    ) -> None:
        async def handler() -> None:
            raise exc

        add_route("/boom", handler)
        response = await client.get("/boom")

        assert response.status_code == expected_status
        body = response.json()["error"]
        assert body["code"] == expected_code
        assert body["retryable"] is retryable

    async def test_retryable_flag_tells_the_caller_what_to_do(
        self, add_route: Callable[[str, Callable[[], Any]], None], client: AsyncClient
    ) -> None:
        async def handler() -> None:
            raise DependencyError("redis unreachable")

        add_route("/boom", handler)
        assert (await client.get("/boom")).json()["error"]["retryable"] is True

    async def test_unexpected_exception_is_masked_in_production(self) -> None:
        """A traceback names internal paths and library versions. Clients get none of it."""
        settings = ApiSettings(environment="production", log_level="CRITICAL")
        app = create_app(settings)
        app.state.settings = settings

        async def handler() -> None:
            raise RuntimeError("password=hunter2 in connection string")

        app.add_api_route("/boom", handler, methods=["GET"])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as http:
            response = await http.get("/boom")

        assert response.status_code == 500
        body = response.json()["error"]
        assert body["message"] == "internal server error"
        assert "hunter2" not in response.text

    async def test_unexpected_exception_is_surfaced_outside_production(
        self, add_route: Callable[[str, Callable[[], Any]], None], client: AsyncClient
    ) -> None:
        async def handler() -> None:
            raise RuntimeError("polygon has one vertex")

        add_route("/boom", handler)
        response = await client.get("/boom")

        assert response.status_code == 500
        assert response.json()["error"]["message"] == "polygon has one vertex"

    async def test_error_responses_still_carry_a_correlation_id(
        self, add_route: Callable[[str, Callable[[], Any]], None], client: AsyncClient
    ) -> None:
        """Without this, the one request worth investigating is the one you cannot find."""

        async def handler() -> None:
            raise RuntimeError("boom")

        add_route("/boom", handler)
        response = await client.get("/boom", headers={REQUEST_ID_HEADER: "trace-err"})

        assert response.headers[REQUEST_ID_HEADER] == "trace-err"


class TestOpenApiSurface:
    def test_docs_are_disabled_in_production(self) -> None:
        app: FastAPI = create_app(ApiSettings(environment="production", log_level="CRITICAL"))
        assert app.docs_url is None
        assert app.openapi_url is None

    def test_docs_are_available_outside_production(self, app: FastAPI) -> None:
        assert app.docs_url == "/docs"

    def test_privacy_posture_is_documented_in_the_openapi_description(self, app: FastAPI) -> None:
        """The API's own description states the prohibitions. It is the first
        thing an integrator reads, and the first thing a reviewer checks."""
        assert app.description is not None
        for phrase in ("no face recognition", "no re-identification", "0004"):
            assert phrase in app.description.lower()
