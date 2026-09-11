"""Credentials must never reach a log line.

RTSP URLs carry passwords, and they most often arrive inside an exception string
rather than as a named field. Both paths are tested.
"""

from __future__ import annotations

import json

import pytest
import structlog

from mansour_common.logging import (
    configure_logging,
    get_correlation_id,
    get_logger,
    set_correlation_id,
)


@pytest.fixture(autouse=True)
def _reset_structlog() -> None:
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()


def _capture() -> structlog.testing.CapturingLogger:
    """Configure structlog to capture rendered events in memory."""
    logger = structlog.testing.CapturingLogger()
    configure_logging(service="test-service", level="DEBUG", render="json")
    structlog.configure(
        processors=structlog.get_config()["processors"],
        logger_factory=lambda *_: logger,
        cache_logger_on_first_use=False,
    )
    return logger


def _rendered(logger: structlog.testing.CapturingLogger) -> dict[str, object]:
    assert logger.calls, "expected exactly one log call"
    payload = logger.calls[-1].args[0]
    result: dict[str, object] = json.loads(payload)
    return result


class TestRedaction:
    def test_secret_named_fields_are_redacted(self) -> None:
        logger = _capture()
        get_logger().info("camera.connect", password="hunter2", api_key="abc123")

        event = _rendered(logger)

        assert event["password"] == "***redacted***"
        assert event["api_key"] == "***redacted***"

    def test_credentials_inside_a_url_are_redacted(self) -> None:
        logger = _capture()
        get_logger().info("camera.connect", url="rtsp://admin:s3cret@192.168.1.42:554/stream")

        event = _rendered(logger)

        assert event["url"] == "rtsp://admin:***redacted***@192.168.1.42:554/stream"
        assert "s3cret" not in json.dumps(event)

    def test_credentials_inside_the_message_body_are_redacted(self) -> None:
        """The realistic case: a connection error whose message embeds the URL."""
        logger = _capture()
        get_logger().error("failed to open rtsp://admin:s3cret@10.0.0.5/live")

        assert "s3cret" not in json.dumps(_rendered(logger))

    def test_source_url_is_redacted_wholesale(self) -> None:
        """`source_url` is a secret reference; even its shape is not logged."""
        logger = _capture()
        get_logger().info("camera.registered", source_url="rtsp://host/stream")

        assert _rendered(logger)["source_url"] == "***redacted***"

    def test_ordinary_urls_survive_intact(self) -> None:
        logger = _capture()
        get_logger().info("probe", endpoint="https://example.test/healthz")

        assert _rendered(logger)["endpoint"] == "https://example.test/healthz"


class TestCorrelationId:
    def test_absent_by_default(self) -> None:
        assert get_correlation_id() is None

    def test_bound_id_appears_on_every_event(self) -> None:
        logger = _capture()
        set_correlation_id("abc123")

        get_logger().info("work.started")

        assert _rendered(logger)["correlation_id"] == "abc123"

    def test_can_be_cleared(self) -> None:
        set_correlation_id("abc123")
        set_correlation_id(None)
        assert get_correlation_id() is None


class TestProductionLoggerFactory:
    """Regression: the configured production factory is `PrintLogger`, which has
    no `.name`. A processor that assumed a stdlib logger crashed on every
    warning and error line — the paths least likely to be exercised in a happy-
    path test and most likely to be needed at 3am."""

    @pytest.mark.parametrize("method", ["debug", "info", "warning", "error", "critical"])
    def test_every_level_renders_without_raising(
        self, method: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        configure_logging(service="test-service", level="DEBUG", render="json")

        getattr(get_logger("mansour.test"), method)("event.happened", camera="cam-1")

        line = capsys.readouterr().out.strip()
        assert json.loads(line)["logger"] == "mansour.test"

    def test_a_logger_created_before_configuration_still_renders_json(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Regression. Modules do `log = get_logger(__name__)` at import time,
        which runs before `configure_logging()`. If `get_logger` resolves the
        configuration eagerly it freezes structlog's unconfigured default — a
        console renderer — and the service's own log lines become unparseable by
        its log pipeline, while the stdlib bridge goes on emitting JSON."""
        module_level_logger = get_logger("mansour.imported.early")

        configure_logging(service="test-service", level="DEBUG", render="json")
        module_level_logger.info("service.started", port=8000)

        line = capsys.readouterr().out.strip()
        event = json.loads(line)  # would raise if the console renderer had won
        assert event["event"] == "service.started"
        assert event["logger"] == "mansour.imported.early"
        assert event["port"] == 8000

    def test_exception_info_is_rendered(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(service="test-service", level="DEBUG", render="json")

        try:
            raise RuntimeError("detector died")
        except RuntimeError:
            get_logger("mansour.test").exception("worker.crashed")

        event = json.loads(capsys.readouterr().out.strip())
        assert "detector died" in event["exception"]


def test_configure_logging_rejects_unknown_level() -> None:
    with pytest.raises(ValueError, match="unknown log level"):
        configure_logging(service="x", level="LOUD")


def test_configure_logging_is_idempotent() -> None:
    """uvicorn imports the app module more than once under --reload."""
    configure_logging(service="test-service")
    configure_logging(service="test-service")

    import logging

    assert len(logging.getLogger().handlers) == 1
