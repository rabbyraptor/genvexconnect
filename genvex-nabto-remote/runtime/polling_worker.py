"""SDK-independent, serial read-only Genvex snapshot worker.

This accepts only an injected authorized RPC45 reader. It does NOT contain
SDK API bindings, credentials, any network listener, or demo live values.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Awaitable, Callable, Sequence

from sensor_model import SENSORS, decode_readings, remote_hostname

ReadFiveRawValues = Callable[[str, tuple[int, ...]], Awaitable[Sequence[int]]]


class PollFailed(Exception):
    """Read-only RPC timed out, disconnected or returned malformed data."""


class ReadOnlyPoller:
    """Single-flight five-value poller; no overlapping remote RPC calls."""

    def __init__(self, *, device_id: str, reader: ReadFiveRawValues,
                 timeout_seconds: float = 30.0) -> None:
        self.device_id = device_id
        self.hostname = remote_hostname(device_id)
        if not callable(reader):
            raise ValueError("A read-only RPC45 callback is required")
        if not isinstance(timeout_seconds, (float, int)) or isinstance(timeout_seconds, bool) or not 1 <= timeout_seconds <= 75:
            raise ValueError("Timeout must be between 1 and 75 seconds")
        self.reader = reader
        self.timeout_seconds = float(timeout_seconds)
        self._lock = asyncio.Lock()
        self._addresses = tuple(sensor.address for sensor in SENSORS)

    async def poll_once(self) -> dict:
        """Return one complete UTC snapshot after one successful RPC45 call."""
        async with self._lock:
            try:
                raw = await asyncio.wait_for(
                    self.reader(self.hostname, self._addresses),
                    timeout=self.timeout_seconds,
                )
                values = decode_readings(raw)
            except asyncio.CancelledError:
                raise
            except Exception:
                # No secret or untrusted SDK/server error text is propagated.
                raise PollFailed("Remote five-sensor read failed") from None
            # Timestamp is produced only after all five values are validated.
            return {
                "schema_version": 1,
                "device_id": self.device_id,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "health": "ok",
                "values": values,
            }
