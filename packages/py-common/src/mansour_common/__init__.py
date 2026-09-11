"""Cross-cutting infrastructure shared by every MANSOUR Vision Python service.

Nothing in this package knows about cameras, zones, crowds, or horses. It is the
substrate the domain services are built on: time, configuration, logging, errors,
identifiers, health, and process lifecycle.
"""

from __future__ import annotations

__version__ = "0.1.0"

from mansour_common.clock import Clock, SystemClock, isoformat, to_utc, utcnow
from mansour_common.errors import (
    ConfigurationError,
    ConflictError,
    ContractViolationError,
    DependencyError,
    MansourError,
    ValidationError,
)
from mansour_common.health import HealthRegistry, ReadinessReport, Status
from mansour_common.ids import correlation_id, deterministic_id, new_id
from mansour_common.logging import configure_logging, get_logger, set_correlation_id

__all__ = [
    "Clock",
    "ConfigurationError",
    "ConflictError",
    "ContractViolationError",
    "DependencyError",
    "HealthRegistry",
    "MansourError",
    "ReadinessReport",
    "Status",
    "SystemClock",
    "ValidationError",
    "__version__",
    "configure_logging",
    "correlation_id",
    "deterministic_id",
    "get_logger",
    "isoformat",
    "new_id",
    "set_correlation_id",
    "to_utc",
    "utcnow",
]
