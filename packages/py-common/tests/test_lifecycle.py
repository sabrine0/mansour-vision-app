"""Graceful shutdown.

The contract: SIGTERM drains, the drain is bounded, and a crash is reported as a
non-zero exit code rather than swallowed.
"""

from __future__ import annotations

import asyncio

from mansour_common.lifecycle import run_service


class _Body:
    """Runs until asked to stop, then finishes within `drain_seconds`."""

    def __init__(self, drain_seconds: float = 0.0) -> None:
        self.drain_seconds = drain_seconds
        self.started = False
        self.finished = False

    async def run(self, stopping: asyncio.Event) -> None:
        self.started = True
        await stopping.wait()
        await asyncio.sleep(self.drain_seconds)
        self.finished = True


class _CrashingBody:
    async def run(self, stopping: asyncio.Event) -> None:
        raise RuntimeError("detector thread died")


class _ImmediateBody:
    async def run(self, stopping: asyncio.Event) -> None:
        return None


async def _stop_after(delay: float, body_started: asyncio.Event) -> None:
    await body_started.wait()
    await asyncio.sleep(delay)


async def test_body_that_returns_exits_zero() -> None:
    assert await run_service(_ImmediateBody()) == 0


async def test_crash_exits_non_zero() -> None:
    """A worker that dies must not report success; the orchestrator restarts it."""
    assert await run_service(_CrashingBody()) == 1


async def test_signal_triggers_graceful_drain() -> None:
    body = _Body(drain_seconds=0.01)

    task = asyncio.create_task(run_service(body, grace_seconds=5))
    await asyncio.sleep(0.05)
    _raise_sigterm()

    exit_code = await asyncio.wait_for(task, timeout=2)

    assert exit_code == 0
    assert body.started
    assert body.finished, "graceful drain must let in-flight work complete"


async def test_drain_that_overruns_the_grace_period_is_cut_short() -> None:
    """A worker that will not die holds its cameras hostage: the scheduler cannot
    re-home them until the lease is released."""
    body = _Body(drain_seconds=10)

    task = asyncio.create_task(run_service(body, grace_seconds=0.05))
    await asyncio.sleep(0.05)
    _raise_sigterm()

    exit_code = await asyncio.wait_for(task, timeout=2)

    assert exit_code == 124
    assert not body.finished


async def test_on_shutdown_hook_runs() -> None:
    closed = False

    async def close() -> None:
        nonlocal closed
        closed = True

    await run_service(_ImmediateBody(), on_shutdown=close)

    assert closed


async def test_on_shutdown_failure_is_reported() -> None:
    async def boom() -> None:
        raise RuntimeError("could not close pool")

    assert await run_service(_ImmediateBody(), on_shutdown=boom) == 1


def _raise_sigterm() -> None:
    """Deliver SIGTERM to this process, portably.

    Windows has no SIGTERM delivery via `os.kill` for the current process, so the
    installed handler is invoked directly. On POSIX the real signal path is
    exercised.
    """
    import os
    import signal
    import sys

    if sys.platform == "win32":
        handler = signal.getsignal(signal.SIGTERM)
        assert callable(handler), "run_service must install a SIGTERM handler"
        handler(signal.SIGTERM, None)
    else:
        os.kill(os.getpid(), signal.SIGTERM)
