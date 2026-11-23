"""V4 snapshot cache exposing independently versioned v1, v3 and v4."""
from __future__ import annotations

import asyncio

from raw_snapshot_v4 import parse_v4
from raw_snapshot_state_v3 import RawV3SnapshotState, _build_v1_v3_snapshots


class RawV4SnapshotState(RawV3SnapshotState):
    def __init__(self, poller):
        super().__init__(poller)
        self._fan_snapshot = None

    def invalidate(self):
        super().invalidate()
        self._fan_snapshot = None

    async def refresh(self):
        async with self._lock:
            self.current()
            self._generation += 1
            try:
                snapshot = await self._poller.poll_once()
                baseline, raw, level = parse_v4(
                    snapshot, expected_device_id=self._poller.device_id)
            except asyncio.CancelledError:
                self.invalidate()
                raise
            except Exception:
                self.invalidate()
                return False
            self._snapshot, self._raw_snapshot = _build_v1_v3_snapshots(
                device_id=self._poller.device_id,
                timestamp_utc=snapshot["timestamp_utc"],
                baseline=baseline,
                raw=raw,
            )
            self._fan_snapshot = {
                **self._raw_snapshot, "schema_version": 4, "fan_level": level,
            }
            return True

    def current_v4(self):
        if self.current_v3() is None:
            self._fan_snapshot = None
            return None
        result = self._fan_snapshot
        if result is None:
            return None
        try:
            parse_v4(result, expected_device_id=self._poller.device_id)
        except Exception:
            self.invalidate()
            return None
        return {
            **{key: result[key] for key in (
                "schema_version", "device_id", "timestamp_utc",
                "health", "fan_level")},
            "values": dict(result["values"]),
            "raw_values": dict(result["raw_values"]),
            "optional": {
                "raw_registers": dict(result["optional"]["raw_registers"])
            },
        }
