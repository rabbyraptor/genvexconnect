"""Strict HA-side v4 fan-stage snapshot validation."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .raw_snapshot_v3 import validate_raw_v3
from .snapshot import InvalidSnapshot


def validate_v4(payload: Any, *, expected_device_id: str,
                now: datetime | None = None):
    if (type(payload) is not dict or set(payload) != {
        "schema_version", "device_id", "timestamp_utc", "health",
        "values", "raw_values", "optional", "fan_level",
    } or type(payload["schema_version"]) is not int
            or payload["schema_version"] != 4):
        raise InvalidSnapshot("Invalid v4 snapshot schema")
    stage = payload["fan_level"]
    if stage is not None and (type(stage) is not int or not 0 <= stage <= 4):
        raise InvalidSnapshot("Invalid fan stage")
    v3 = {k: v for k, v in payload.items() if k not in ("fan_level", "schema_version")}
    v3["schema_version"] = 3
    values, raw = validate_raw_v3(
        v3, expected_device_id=expected_device_id, now=now,
    )
    return values, raw, stage
