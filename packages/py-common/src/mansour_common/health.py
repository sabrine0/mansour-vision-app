"""Liveness and readiness.

The distinction is operational, not cosmetic, and getting it backwards causes
outages:

* **Liveness** (`/healthz`) answers *is this process wedged?* It must not depend
  on anything external. A database outage that fails liveness gets every service
  replica killed by the orchestrator, turning a recoverable dependency failure
  into a total one.
* **Readiness** (`/readyz`) answers *should traffic be sent here?* It probes real
  dependencies.

Volume II §25 (degraded operation) requires that a dependency failure degrade the
platform rather than stop it. That table is implemented here: a check is declared
`critical` only when the service genuinely cannot do its job without it. The
`vision-worker` keeps detecting when PostgreSQL is down, so PostgreSQL is not a
critical check for the worker — it is for `core-api`.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from mansour_common.logging import get_logger

log = get_logger(__name__)

#: A check returns None on success, or raises. Its exception message is reported.
CheckFn = Callable[[], Awaitable[None]]


class Status(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    status: Status
    critical: bool
    duration_ms: float
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status.value,
            "critical": self.critical,
            "duration_ms": round(self.duration_ms, 2),
        }
        if self.detail is not None:
            payload["detail"] = self.detail
        return payload


@dataclass(frozen=True, slots=True)
class _Check:
    name: str
    fn: CheckFn
    critical: bool
    timeout_seconds: float


@dataclass(slots=True)
class ReadinessReport:
    status: Status
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        """Traffic may be routed here.

        A degraded service is still ready: it has lost a non-critical dependency
        and must keep serving, saying plainly what it no longer knows
        (Volume II §2.7). Only a failed critical check withdraws it from service.
        """
        return self.status is not Status.FAILED

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "checks": {c.name: c.as_dict() for c in self.checks},
        }


class HealthRegistry:
    """Collects dependency probes and evaluates them concurrently.

    Results are cached for `cache_seconds`. Kubernetes and Docker probe
    readiness every few seconds; without a cache, a fleet of replicas becomes a
    denial-of-service against its own database.
    """

    def __init__(self, *, cache_seconds: float = 2.0) -> None:
        if cache_seconds < 0:
            raise ValueError("cache_seconds must not be negative")
        self._checks: list[_Check] = []
        self._cache_seconds = cache_seconds
        self._cached: ReadinessReport | None = None
        self._cached_at = 0.0
        self._lock = asyncio.Lock()

    def register(
        self,
        name: str,
        fn: CheckFn,
        *,
        critical: bool = True,
        timeout_seconds: float = 3.0,
    ) -> None:
        """Register a dependency probe.

        `critical=False` means the service degrades but keeps serving when this
        dependency is unavailable.
        """
        if any(c.name == name for c in self._checks):
            raise ValueError(f"health check {name!r} is already registered")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._checks.append(_Check(name, fn, critical, timeout_seconds))

    async def check(self, *, use_cache: bool = True) -> ReadinessReport:
        now = time.monotonic()
        if use_cache and self._cached is not None and now - self._cached_at < self._cache_seconds:
            return self._cached

        async with self._lock:
            # Another coroutine may have refreshed the cache while we waited.
            now = time.monotonic()
            if (
                use_cache
                and self._cached is not None
                and now - self._cached_at < self._cache_seconds
            ):
                return self._cached

            results = await asyncio.gather(*(self._run(c) for c in self._checks))
            report = ReadinessReport(status=_aggregate(results), checks=list(results))
            self._cached = report
            self._cached_at = time.monotonic()
            return report

    async def _run(self, check: _Check) -> CheckResult:
        started = time.perf_counter()
        try:
            await asyncio.wait_for(check.fn(), timeout=check.timeout_seconds)
        except TimeoutError:
            elapsed = (time.perf_counter() - started) * 1000
            log.warning("health.check.timeout", check=check.name, timeout=check.timeout_seconds)
            return CheckResult(
                check.name,
                Status.FAILED,
                check.critical,
                elapsed,
                f"timed out after {check.timeout_seconds}s",
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - started) * 1000
            log.warning("health.check.failed", check=check.name, error=str(exc))
            return CheckResult(check.name, Status.FAILED, check.critical, elapsed, str(exc))

        elapsed = (time.perf_counter() - started) * 1000
        return CheckResult(check.name, Status.OK, check.critical, elapsed)


def _aggregate(results: list[CheckResult]) -> Status:
    if any(r.status is Status.FAILED and r.critical for r in results):
        return Status.FAILED
    if any(r.status is Status.FAILED for r in results):
        return Status.DEGRADED
    return Status.OK


__all__ = [
    "CheckResult",
    "HealthRegistry",
    "ReadinessReport",
    "Status",
]
