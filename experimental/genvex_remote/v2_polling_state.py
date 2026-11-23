"""Opt-in, SDK-independent atomic seven-address polling and snapshot state.

This module is inert on import and does not replace the production v1 poller.
The caller must inject an authorized, read-only RPC45 adapter; no SDK, sockets,
credentials, HTTP server, tasks, or live polling are started here.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Awaitable, Callable, Sequence

from sensor_model import remote_hostname
from seven_read_plan_v2_draft import ORDERED_ADDRESSES, decode_seven_to_v2
from snapshot_contract import SnapshotError
from snapshot_v2_draft import parse_v2

SevenRead = Callable[[str, tuple[int, ...]], Awaitable[Sequence[int]]]


class V2PollFailed(Exception):
    """No fresh, complete baseline could be obtained."""


class ReadOnlyV2Poller:
    """Single-flight, exactly-seven-address RPC45 reader (no automatic retry)."""

    def __init__(self, *, device_id: str, reader: SevenRead,
                 timeout_seconds: float = 30.0) -> None:
        self.device_id = device_id
        self.hostname = remote_hostname(device_id)
        if not callable(reader):
            raise ValueError("Authorized read-only callback required")
        if (type(timeout_seconds) not in (int, float)
                or not 1 <= timeout_seconds <= 75):
            raise ValueError("Timeout must be between 1 and 75 seconds")
        self._reader = reader
        self._timeout = float(timeout_seconds)
        self._lock = asyncio.Lock()

    async def poll_once(self) -> dict:
        async with self._lock:
            try:
                raw = await asyncio.wait_for(
                    self._reader(self.hostname, ORDERED_ADDRESSES),
                    timeout=self._timeout,
                )
                return decode_seven_to_v2(
                    raw, device_id=self.device_id,
                    measured_at=datetime.now(timezone.utc),
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                raise V2PollFailed("Remote v2 read unavailable") from None


class V2SnapshotState:
    """Expose only a fresh atomic v2 snapshot; failures invalidate prior data."""

    def __init__(self, poller: ReadOnlyV2Poller):
        self._poller = poller
        self._snapshot: dict | None = None
        self._lock = asyncio.Lock()
        self._generation = 0

    async def refresh(self) -> bool:
        async with self._lock:
            self._snapshot = None
            self._generation += 1
            try:
                payload = await self._poller.poll_once()
                parse_v2(payload, expected_device_id=self._poller.device_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                return False
            self._snapshot = payload
            return True

    def current(self) -> dict | None:
        payload = self._snapshot
        if payload is None:
            return None
        try:
            base, fans = parse_v2(
                payload, expected_device_id=self._poller.device_id
            )
        except (SnapshotError, ValueError, TypeError):
            self._snapshot = None
            return None
        return {
            "schema_version": 2,
            "device_id": self._poller.device_id,
            "timestamp_utc": payload["timestamp_utc"],
            "health": "ok",
            "values": dict(base),
            "optional": {"fan_duty": dict(fans)},
        }

    def invalidate(self) -> None:
        self._snapshot = None

    @property
    def device_id(self) -> str:
        return self._poller.device_id

    @property
    def generation(self) -> int:
        return self._generation
