"""Bounded, single-owner, read-only polling lifecycle (no SDK or HTTP).

Inject a ReadOnlyPoller backed by an authorized RPC45 adapter in a future App.
Does not start a service, store secrets, expose ports or run on import.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Callable, Awaitable

from snapshot_state import SnapshotState


class PollingService:
    """Schedule serial reads and make failures unavailable immediately."""

    def __init__(self, state: SnapshotState, *, interval_seconds: float = 60,
                 on_result: Callable[[bool], Awaitable[None]] | None = None):
        if not isinstance(interval_seconds, (float, int)) or isinstance(interval_seconds, bool) or not 1 <= interval_seconds <= 3600:
            raise ValueError("Invalid interval")
        self.state = state
        self.interval_seconds = float(interval_seconds)
        self.on_result = on_result
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        """Begin immediate first poll; fail closed if already running."""
        if self.running:
            raise RuntimeError("Polling service already started")
        self._stop = asyncio.Event()
        self._task = asyncio.create_task(self._loop(), name="genvex_remote_readonly_poll")

    async def stop(self) -> None:
        """Stop at any point, including during a long RPC; clear cached data."""
        self._stop.set()
        task = self._task
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._task = None
        self.state.invalidate()

    async def _loop(self) -> None:
        """Never overlap polls and avoid catch-up bursts after slow requests."""
        while not self._stop.is_set():
            # Keep the log strictly metadata-only; no SDK responses or secrets.
            adapter = getattr(self.state, "_poller", None)
            before_pid = getattr(getattr(adapter, "_proc", None), "pid", None)
            started = time.monotonic()
            try:
                ok = await self.state.refresh()
            except asyncio.CancelledError:
                raise
            except Exception:
                # An unexpected internal failure must not terminate the
                # scheduled poll loop or leave the last snapshot available.
                # Never log the exception: it may contain SDK secrets.
                self.state.invalidate()
                ok = False
            elapsed = time.monotonic() - started
            after_pid = getattr(getattr(adapter, "_proc", None), "pid", None)
            timestamp = datetime.now(timezone.utc).isoformat()
            status = "OK" if ok else "FEJL"
            print(
                f"RPC45 {timestamp} {status} {elapsed:.2f}s "
                f"PID_BEFORE={before_pid} PID_AFTER={after_pid}",
                flush=True,
            )
            if self.on_result is not None:
                try:
                    await self.on_result(ok)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    # Reporting failures must not kill the read loop.
                    pass
            try:
                await asyncio.wait_for(self._stop.wait(), self.interval_seconds)
            except asyncio.TimeoutError:
                continue
