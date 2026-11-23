"""DEV8.3 v3 atomic state: v1 projection remains independently usable.

One serial persistent worker produces a five-value baseline and an optional
twelve-raw group. Missing extra readings never invalidate the five legacy
readings; a failed mandatory baseline invalidates both projections.
"""
from __future__ import annotations

import asyncio
from typing import Any

from raw_registers_v3 import BASE_KEYS, OPTIONAL_KEYS, parse_raw_v3
from snapshot_contract import SnapshotError
from snapshot_state import SnapshotState


def _build_v1_v3_snapshots(
    *, device_id: str, timestamp_utc: str,
    baseline: dict[str, float], raw: dict[str, int],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build both detached wire projections from one validated read.

    This function owns only snapshot construction. V3 and v4 must still
    validate their respective inputs independently before calling it.
    Only whitelisted fields reach the HTTP snapshot cache.
    """
    common = {
        "device_id": device_id,
        "timestamp_utc": timestamp_utc,
        "health": "ok",
    }
    legacy = {
        "schema_version": 1,
        **common,
        "values": dict(baseline),
    }
    expanded = {
        "schema_version": 3,
        **common,
        "values": dict(baseline),
        "raw_values": {key: raw[key] for key in BASE_KEYS},
        "optional": {
            "raw_registers": {
                key: raw[key] for key in OPTIONAL_KEYS if key in raw
            },
        },
    }
    return legacy, expanded


class RawV3SnapshotState(SnapshotState):
    """Own v3 snapshot and project exact v1 data without new SDK reads."""

    def __init__(self, poller):
        super().__init__(poller)
        self._raw_snapshot: dict[str, Any] | None = None

    def invalidate(self) -> None:
        super().invalidate()
        self._raw_snapshot = None

    async def refresh(self) -> bool:
        async with self._lock:
            self.current()
            self._generation += 1
            try:
                snapshot = await self._poller.poll_once()
                baseline, raw = parse_raw_v3(
                    snapshot, expected_device_id=self._poller.device_id,
                )
            except asyncio.CancelledError:
                self.invalidate()
                raise
            except Exception as exc:
                # Preserve the existing metadata-only SDK diagnostic contract.
                status = getattr(exc, "rpc_status", None)
                elapsed = getattr(exc, "elapsed_ms", None)
                if (
                    type(status) is int and 0 <= status <= 100000
                    and type(elapsed) is int and 0 <= elapsed <= 120000
                ):
                    print(
                        f"RPC45_DIAGNOSTIC rpc_status={status} elapsed_ms={elapsed}",
                        flush=True,
                    )
                self.invalidate()
                return False

            # The same projection function serves both v3 and v4 caches.
            self._snapshot, self._raw_snapshot = _build_v1_v3_snapshots(
                device_id=self._poller.device_id,
                timestamp_utc=snapshot["timestamp_utc"],
                baseline=baseline,
                raw=raw,
            )
            return True

    def current_v3(self) -> dict[str, Any] | None:
        """Return only a fresh detached raw snapshot, no SDK work."""
        if self.current() is None:
            self._raw_snapshot = None
            return None
        snapshot = self._raw_snapshot
        if snapshot is None:
            return None
        try:
            parse_raw_v3(snapshot, expected_device_id=self._poller.device_id)
        except SnapshotError:
            self.invalidate()
            return None
        return {
            **{field: snapshot[field] for field in (
                "schema_version", "device_id", "timestamp_utc", "health",
            )},
            "values": dict(snapshot["values"]),
            "raw_values": dict(snapshot["raw_values"]),
            "optional": {
                "raw_registers": dict(snapshot["optional"]["raw_registers"]),
            },
        }
