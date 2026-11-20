"""An atomic, fail-closed view of the most recent successful five-sensor read.

This is an in-process prototype; no network, real account or SDK is loaded.
Read failures clear prior success immediately, avoiding stale 'live' readings.
"""
from __future__ import annotations

import asyncio
from typing import Any

from polling_worker import ReadOnlyPoller
from snapshot_contract import SnapshotError, parse_snapshot


class SnapshotState:
    """Owns one producer task and one immutable validated result at a time."""

    def __init__(self, poller: ReadOnlyPoller):
        self._poller = poller
        self._snapshot: dict[str, Any] | None = None
        self._lock = asyncio.Lock()
        self._generation = 0

    async def refresh(self) -> bool:
        """Serialize refreshes; never retain an older value after RPC failure."""
        async with self._lock:
            # Clears the prior data *before* any potentially slow I/O.
            self._snapshot = None
            self._generation += 1
            try:
                result = await self._poller.poll_once()
                parse_snapshot(result, expected_device_id=self._poller.device_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                return False
            self._snapshot = result
            return True

    def invalidate(self) -> None:
        """Immediately remove any last snapshot (shutdown / offline state)."""
        self._snapshot = None

    def current(self) -> dict[str, Any] | None:
        """Return a detached copy only if it remains complete and fresh."""
        result = self._snapshot
        if result is None:
            return None
        try:
            parse_snapshot(result, expected_device_id=self._poller.device_id)
        except SnapshotError:
            self._snapshot = None
            return None
        return {
            "schema_version": result["schema_version"],
            "device_id": result["device_id"],
            "timestamp_utc": result["timestamp_utc"],
            "health": result["health"],
            "values": dict(result["values"]),
        }

    @property
    def generation(self) -> int:
        return self._generation
