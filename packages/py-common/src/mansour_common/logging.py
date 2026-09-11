"""Structured logging.

Logs are JSON on stdout and are shipped by the platform, never written to a
database table (`docs/architecture/data-model.md`: a `logs` table competes for
write IOPS with the telemetry that pays for the database).

Two invariants this module enforces:

1. **Correlation.** Every log line emitted while handling a request or a stream
   message carries the same `correlation_id`, so one incident's trail can be
   reconstructed across services.
2. **Secret redaction.** Camera RTSP URLs carry credentials (ADR: `source_url`
   holds a secret reference, never the credential). Anything that slips through
   is redacted at the last possible moment, in the log pipeline, because that is
   the only place with a complete view of what is about to be written.
"""

from __future__ import annotations

import logging
import re
import sys
from contextvars import ContextVar
from typing import Any, Literal

import structlog
from structlog.types import EventDict, Processor

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)

# Matches credentials embedded in a URL authority: scheme://user:password@host
_URL_CREDENTIALS = re.compile(r"(?P<scheme>\w+://)(?P<user>[^:/@\s]+):(?P<pw>[^@/\s]+)@")

# Keys whose values are never safe to log, whatever their content.
_SECRET_KEYS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "api_key",
        "private_key",
        "source_url",
        "rtsp_url",
        "database_url",
        "redis_url",
    }
)

_REDACTED = "***redacted***"


def set_correlation_id(value: str | None) -> None:
    """Bind a correlation id to the current context (request, task, or message)."""
    _correlation_id.set(value)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def _inject_correlation_id(_: object, __: str, event_dict: EventDict) -> EventDict:
    cid = _correlation_id.get()
    if cid is not None:
        event_dict.setdefault("correlation_id", cid)
    return event_dict


class _NamedPrintLogger(structlog.PrintLogger):
    """A `PrintLogger` that carries the name it was created with."""

    def __init__(self, file: Any = None, name: str | None = None) -> None:
        super().__init__(file)
        self.name = name


class _NamedPrintLoggerFactory:
    """A `PrintLoggerFactory` that remembers the logger's name.

    `structlog.PrintLoggerFactory` discards the name passed to `get_logger(name)`,
    so `_add_logger_name` below would have nothing to read. Attaching the name to
    the logger instance is what lets `get_logger` stay lazy: the alternative —
    `get_logger(name).bind(logger=name)` — resolves the configuration at import
    time, freezing structlog's unconfigured console default into every module's
    module-level logger.
    """

    __slots__ = ("_file",)

    def __init__(self, file: Any) -> None:
        self._file = file

    def __call__(self, *args: Any) -> _NamedPrintLogger:
        name = args[0] if args else None
        return _NamedPrintLogger(self._file, name)


def _add_logger_name(logger: object, _: str, event_dict: EventDict) -> EventDict:
    """Attach the logger's name, whatever kind of logger produced the event.

    `structlog.stdlib.add_logger_name` reads `logger.name` unconditionally, which
    raises for the `PrintLogger` this module configures in production. The same
    chain must serve both structlog-native loggers and stdlib records forwarded
    through `ProcessorFormatter`, so the lookup is defensive.
    """
    if "logger" in event_dict:
        return event_dict
    record = event_dict.get("_record")
    name = getattr(record, "name", None) or getattr(logger, "name", None)
    if name:
        event_dict["logger"] = name
    return event_dict


def _redact_url_credentials(value: str) -> str:
    return _URL_CREDENTIALS.sub(r"\g<scheme>\g<user>:" + _REDACTED + "@", value)


def _redact(_: object, __: str, event_dict: EventDict) -> EventDict:
    """Strip credentials from log records.

    Applied to every event, including the message body, because a URL with a
    password in it most often arrives inside an exception string rather than as
    a named field.
    """
    for key, value in list(event_dict.items()):
        if key.lower() in _SECRET_KEYS:
            event_dict[key] = _REDACTED
        elif isinstance(value, str) and "://" in value:
            event_dict[key] = _redact_url_credentials(value)
    return event_dict


def configure_logging(
    *,
    service: str,
    level: str = "INFO",
    render: Literal["json", "console"] = "json",
) -> None:
    """Configure structlog and the stdlib logging bridge for a service process.

    Idempotent: calling twice reconfigures rather than double-registering, which
    matters because uvicorn imports the app module more than once under reload.
    """
    numeric_level = logging.getLevelName(level.upper())
    if not isinstance(numeric_level, int):
        raise ValueError(f"unknown log level: {level!r}")

    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        _inject_correlation_id,
        structlog.stdlib.add_log_level,
        _add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        _redact,
    ]

    renderer: Processor = (
        structlog.processors.JSONRenderer()
        if render == "json"
        else structlog.dev.ConsoleRenderer(colors=False)
    )

    structlog.configure(
        processors=[
            *shared,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=_NamedPrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Route stdlib loggers (uvicorn, sqlalchemy, redis) through the same pipeline
    # so a service emits exactly one log format.
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
        )
    )
    root.addHandler(handler)
    root.setLevel(numeric_level)

    # uvicorn installs its own handlers; drop them so lines are not emitted twice.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    structlog.contextvars.bind_contextvars(service=service)


def get_logger(name: str | None = None) -> Any:
    """Return a lazily-bound structlog logger.

    Two constraints meet here.

    The name must be attached as an initial value, because `PrintLoggerFactory` —
    which this module configures in production — discards the name that
    `structlog.get_logger` is given, and log-based alerting needs the `logger`
    field to be reliably present.

    But it must be attached *lazily*. Modules do `log = get_logger(__name__)` at
    import time, which happens before `configure_logging()` runs. Calling
    `.bind()` on the proxy resolves the configuration immediately and freezes
    structlog's unconfigured default — a console renderer — for the lifetime of
    that logger, while the stdlib bridge goes on emitting JSON. The result is a
    process whose own log lines are unparseable by its log pipeline.

    Returning the proxy untouched keeps it lazy. The name reaches the event via
    `_NamedPrintLoggerFactory`, which stores it on the logger instance for
    `_add_logger_name` to read at render time.
    """
    return structlog.get_logger(name) if name is not None else structlog.get_logger()


__all__ = [
    "configure_logging",
    "get_correlation_id",
    "get_logger",
    "set_correlation_id",
]
