"""Process lifecycle for the long-running, non-HTTP services.

`vision-worker`, `alert-engine` and `analytics-consumer` are daemons, not web
servers. They still need what a web server gets for free: signal handling, an
orderly shutdown that lets in-flight work finish, and a health endpoint the
orchestrator can probe.

The shutdown contract, which Volume II §25 depends on:

* SIGTERM begins a graceful drain. `Runnable.stop()` is asked to finish.
* If the drain exceeds `shutdown_grace_seconds`, the process exits anyway. A
  worker that refuses to die holds its cameras hostage; the scheduler cannot
  re-home them until the lease is released.
* A second SIGTERM/SIGINT exits immediately. Operators expect Ctrl-C twice to
  work, and denying them that gets the process `kill -9`ed, which skips cleanup.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
import sys
from collections.abc import Awaitable, Callable
from typing import Protocol

from mansour_common.logging import get_logger

log = get_logger(__name__)


class Runnable(Protocol):
    """A long-running service body."""

    async def run(self, stopping: asyncio.Event) -> None:
        """Do the work until `stopping` is set, then return.

        Implementations must observe `stopping` promptly. Blocking work belongs
        in a thread or a subprocess, never on the event loop.
        """
        ...


async def run_service(
    runnable: Runnable,
    *,
    grace_seconds: float = 15.0,
    on_shutdown: Callable[[], Awaitable[None]] | None = None,
) -> int:
    """Run `runnable` until a termination signal arrives. Returns a process exit code."""
    loop = asyncio.get_running_loop()
    stopping = asyncio.Event()
    force = asyncio.Event()

    def _signal_handler(signame: str) -> None:
        if stopping.is_set():
            log.warning("lifecycle.force_exit", signal=signame)
            force.set()
            return
        log.info("lifecycle.shutdown_requested", signal=signame, grace_seconds=grace_seconds)
        stopping.set()

    _install_signal_handlers(loop, _signal_handler)

    task = asyncio.create_task(runnable.run(stopping), name="service-body")
    # `stopping` must be waited on explicitly. A signal sets the event but does
    # not complete the body task, so waiting only on the body would sleep through
    # the entire shutdown and never start the grace timer.
    stop_signal = asyncio.create_task(stopping.wait(), name="stop-signal")
    forced = asyncio.create_task(force.wait(), name="force-exit")

    exit_code = 0
    try:
        await asyncio.wait({task, stop_signal, forced}, return_when=asyncio.FIRST_COMPLETED)

        if task.done():
            exit_code = _exit_code_from(task)
        elif force.is_set():
            log.error("lifecycle.forced")
            exit_code = 130
        else:
            # Graceful drain, bounded. A second signal cuts it short.
            await asyncio.wait(
                {task, forced}, timeout=grace_seconds, return_when=asyncio.FIRST_COMPLETED
            )
            if task.done():
                exit_code = _exit_code_from(task)
            elif force.is_set():
                log.error("lifecycle.forced")
                exit_code = 130
            else:
                log.error("lifecycle.grace_expired", grace_seconds=grace_seconds)
                exit_code = 124

        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
    finally:
        for pending in (stop_signal, forced):
            pending.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pending

    if on_shutdown is not None:
        try:
            await asyncio.wait_for(on_shutdown(), timeout=grace_seconds)
        except Exception:
            log.exception("lifecycle.on_shutdown_failed")
            exit_code = exit_code or 1

    log.info("lifecycle.stopped", exit_code=exit_code)
    return exit_code


def _exit_code_from(task: asyncio.Task[None]) -> int:
    if task.cancelled():
        return 130
    exc = task.exception()
    if exc is not None:
        log.error("lifecycle.crashed", error=str(exc), exc_info=exc)
        return 1
    return 0


def _install_signal_handlers(
    loop: asyncio.AbstractEventLoop, handler: Callable[[str], None]
) -> None:
    """Install SIGINT/SIGTERM handlers, falling back to `signal.signal` on Windows.

    `loop.add_signal_handler` is not implemented on the Windows Proactor loop,
    and developers run these services on Windows.
    """
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handler, sig.name)
        except NotImplementedError:
            signal.signal(sig, lambda s, _frame: handler(signal.Signals(s).name))


def run(runnable: Runnable, *, grace_seconds: float = 15.0) -> None:
    """Synchronous entrypoint: run the service and exit the process with its code."""
    sys.exit(asyncio.run(run_service(runnable, grace_seconds=grace_seconds)))


__all__ = ["Runnable", "run", "run_service"]
