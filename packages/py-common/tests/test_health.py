"""Readiness semantics.

The behaviour under test is the one Volume II §25 depends on: losing a
non-critical dependency degrades the service but keeps it in rotation; losing a
critical one withdraws it.
"""

from __future__ import annotations

import asyncio

import pytest

from mansour_common.health import HealthRegistry, Status


async def _ok() -> None:
    return None


async def _fail() -> None:
    raise RuntimeError("connection refused")


async def _hang() -> None:
    await asyncio.sleep(10)


class TestAggregation:
    async def test_all_ok(self) -> None:
        registry = HealthRegistry(cache_seconds=0)
        registry.register("postgres", _ok)
        registry.register("redis", _ok)

        report = await registry.check()

        assert report.status is Status.OK
        assert report.ready

    async def test_failed_critical_check_is_not_ready(self) -> None:
        registry = HealthRegistry(cache_seconds=0)
        registry.register("postgres", _fail, critical=True)

        report = await registry.check()

        assert report.status is Status.FAILED
        assert not report.ready

    async def test_failed_non_critical_check_degrades_but_stays_ready(self) -> None:
        """A worker keeps detecting when PostgreSQL is down. Withdrawing it from
        service would convert a recoverable failure into a total one."""
        registry = HealthRegistry(cache_seconds=0)
        registry.register("redis", _ok, critical=True)
        registry.register("postgres", _fail, critical=False)

        report = await registry.check()

        assert report.status is Status.DEGRADED
        assert report.ready

    async def test_no_checks_is_ok(self) -> None:
        report = await HealthRegistry(cache_seconds=0).check()
        assert report.status is Status.OK


class TestFailureReporting:
    async def test_failure_detail_is_captured(self) -> None:
        registry = HealthRegistry(cache_seconds=0)
        registry.register("redis", _fail)

        report = await registry.check()

        (result,) = report.checks
        assert result.status is Status.FAILED
        assert result.detail == "connection refused"

    async def test_slow_check_times_out_rather_than_hanging_the_probe(self) -> None:
        registry = HealthRegistry(cache_seconds=0)
        registry.register("slow", _hang, timeout_seconds=0.05)

        report = await registry.check()

        (result,) = report.checks
        assert result.status is Status.FAILED
        assert result.detail is not None
        assert "timed out" in result.detail

    async def test_serialisation_shape(self) -> None:
        registry = HealthRegistry(cache_seconds=0)
        registry.register("redis", _ok)

        payload = (await registry.check()).as_dict()

        assert payload["status"] == "ok"
        assert payload["checks"]["redis"]["status"] == "ok"
        assert payload["checks"]["redis"]["critical"] is True
        assert isinstance(payload["checks"]["redis"]["duration_ms"], float)


class TestCaching:
    async def test_results_are_cached(self) -> None:
        """Probing every replica's dependencies on every kubelet poll is a
        self-inflicted denial of service."""
        calls = 0

        async def counting() -> None:
            nonlocal calls
            calls += 1

        registry = HealthRegistry(cache_seconds=60)
        registry.register("dep", counting)

        await registry.check()
        await registry.check()
        await registry.check()

        assert calls == 1

    async def test_cache_can_be_bypassed(self) -> None:
        calls = 0

        async def counting() -> None:
            nonlocal calls
            calls += 1

        registry = HealthRegistry(cache_seconds=60)
        registry.register("dep", counting)

        await registry.check()
        await registry.check(use_cache=False)

        assert calls == 2

    async def test_concurrent_probes_collapse_to_one_run(self) -> None:
        calls = 0

        async def counting() -> None:
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)

        registry = HealthRegistry(cache_seconds=60)
        registry.register("dep", counting)

        await asyncio.gather(*(registry.check() for _ in range(10)))

        assert calls == 1


class TestRegistration:
    def test_duplicate_name_is_rejected(self) -> None:
        registry = HealthRegistry()
        registry.register("redis", _ok)
        with pytest.raises(ValueError, match="already registered"):
            registry.register("redis", _ok)

    def test_non_positive_timeout_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="timeout_seconds must be positive"):
            HealthRegistry().register("redis", _ok, timeout_seconds=0)

    def test_negative_cache_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="must not be negative"):
            HealthRegistry(cache_seconds=-1)
