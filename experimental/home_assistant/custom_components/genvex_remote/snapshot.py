"""Self-contained read-only snapshot validation for the HA component.

Mirrors experimental/genvex_remote/snapshot_contract.py; keep schemas in sync
until the runtime and HA packages share a versioned, distributable module.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any

from .const import SENSORS, valid_device_id

class InvalidSnapshot(Exception):
    """Invalid, incomplete, wrong-device or stale snapshot."""


def validate_snapshot(
    snapshot: Any, *, expected_device_id: str,
    now: datetime | None = None, max_age_seconds: int = 180,
) -> dict[str, float]:
    if not valid_device_id(expected_device_id):
        raise InvalidSnapshot("Invalid configured device")
    if not isinstance(snapshot, dict) or set(snapshot) != {
        "schema_version", "device_id", "timestamp_utc", "health", "values"
    }:
        raise InvalidSnapshot("Invalid snapshot schema")
    if type(snapshot["schema_version"]) is not int or snapshot["schema_version"] != 1:
        raise InvalidSnapshot("Unsupported snapshot version")
    if snapshot["device_id"] != expected_device_id or snapshot["health"] != "ok":
        raise InvalidSnapshot("Snapshot unavailable or wrong device")
    try:
        stamp = snapshot["timestamp_utc"]
        if not isinstance(stamp, str) or len(stamp) > 48:
            raise ValueError
        measured = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        current = now or datetime.now(timezone.utc)
        if measured.tzinfo is None or current.tzinfo is None:
            raise ValueError
        age = (current - measured).total_seconds()
    except (ValueError, TypeError, OverflowError):
        raise InvalidSnapshot("Malformed timestamp") from None
    if age > max_age_seconds or age < -30:
        raise InvalidSnapshot("Stale or future snapshot")
    values = snapshot["values"]
    if not isinstance(values, dict) or set(values) != {s.key for s in SENSORS}:
        raise InvalidSnapshot("Incomplete reading batch")
    result = {}
    for item in SENSORS:
        value = values[item.key]
        if type(value) not in (float, int) or not isfinite(value):
            raise InvalidSnapshot("Invalid reading")
        result[item.key] = float(value)
    return result
