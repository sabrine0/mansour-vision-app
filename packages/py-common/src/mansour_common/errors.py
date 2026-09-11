"""The platform's error taxonomy.

Errors are classified by *what the caller should do about them*, not by where
they were raised. That is the only classification a caller can act on.

`retryable` is the distinction the event-spine consumers depend on: ADR 0007
gives at-least-once delivery, so a consumer must decide between redelivering a
message and dead-lettering it. Getting that wrong either loses events or spins
forever on a poisoned one.
"""

from __future__ import annotations

from typing import Any


class MansourError(Exception):
    """Base class for every error this platform raises deliberately."""

    #: Whether retrying the same operation could plausibly succeed.
    retryable: bool = False
    #: Stable, machine-readable identifier. Never a message string.
    code: str = "internal_error"

    def __init__(self, message: str, /, **context: Any) -> None:
        super().__init__(message)
        self.message = message
        #: Structured detail attached to logs. Must never contain secrets.
        self.context = context

    def __str__(self) -> str:
        if not self.context:
            return self.message
        detail = ", ".join(f"{k}={v!r}" for k, v in sorted(self.context.items()))
        return f"{self.message} ({detail})"


class ConfigurationError(MansourError):
    """The service cannot start, or cannot continue, with the configuration given.

    Never retryable: the process must exit and be corrected. A service that
    limps along on invalid configuration is the failure mode Volume II §2.7
    exists to prevent.
    """

    code = "configuration_error"
    retryable = False


class DependencyError(MansourError):
    """A downstream dependency (database, cache, event spine) is unavailable."""

    code = "dependency_unavailable"
    retryable = True


class ValidationError(MansourError):
    """Input failed validation. Retrying with the same input cannot help."""

    code = "validation_error"
    retryable = False


class ContractViolationError(MansourError):
    """A message on the event spine does not satisfy its declared schema.

    Not retryable: the producer emitted something invalid, and redelivering it
    will fail identically. The message is dead-lettered and an operator is told,
    rather than the consumer stalling the whole stream on it.
    """

    code = "contract_violation"
    retryable = False


class ConflictError(MansourError):
    """The operation conflicts with current state (idempotency, optimistic locking)."""

    code = "conflict"
    retryable = False


__all__ = [
    "ConfigurationError",
    "ConflictError",
    "ContractViolationError",
    "DependencyError",
    "MansourError",
    "ValidationError",
]
