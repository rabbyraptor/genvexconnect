"""Pure-Python HA <-> Nabto-runtime read-only snapshot contract.

No Home Assistant imports, network, credentials or device control.
A future authenticated internal transport will carry these documents.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any

from sensor_model import SENSORS, remote_hostname

SCHEMA_VERSION = 1
DEFAULT_MAX_AGE_SECONDS = 180
MAX_FUTURE_SKEW_SECONDS = 30


class SnapshotError(ValueError):
    """Invalid or stale runtime response; HA must mark entities unavailable."""


def parse_snapshot(
    payload: Any, *, expected_device_id: str,
    now: datetime | None = None, max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> dict[str, float]:
    """Accept only a fresh complete snapshot from exactly the configured device."""
    remote_hostname(expected_device_id)
    if (not isinstance(max_age_seconds, int) or isinstance(max_age_seconds, bool)
            or not 10 <= max_age_seconds <= 3600):
        raise ValueError("Invalid snapshot age limit")
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version", "device_id", "timestamp_utc", "health", "values"
    }:
        raise SnapshotError("Invalid snapshot schema")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != SCHEMA_VERSION:
        raise SnapshotError("Unsupported snapshot version")
    if payload["device_id"] != expected_device_id or payload["health"] != "ok":
        raise SnapshotError("Snapshot is not from the available configured device")
    try:
        timestamp = payload["timestamp_utc"]
        if not isinstance(timestamp, str) or len(timestamp) > 48:
            raise ValueError
        measured = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if measured.tzinfo is None:
            raise ValueError
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError
        age = (current - measured).total_seconds()
    except (ValueError, TypeError, OverflowError):
        raise SnapshotError("Malformed snapshot timestamp") from None
    if age > max_age_seconds or age < -MAX_FUTURE_SKEW_SECONDS:
        raise SnapshotError("Snapshot is stale or its timestamp is in the future")
    values = payload["values"]
    expected = {sensor.key for sensor in SENSORS}
    if not isinstance(values, dict) or set(values) != expected:
        raise SnapshotError("Incomplete snapshot values")
    result: dict[str, float] = {}
    for key, reading in values.items():
        if type(reading) not in (float, int) or not isfinite(reading):
            raise SnapshotError("Invalid snapshot reading")
        result[key] = float(reading)
    return result
