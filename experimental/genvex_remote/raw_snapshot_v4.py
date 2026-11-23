"""Strict v4 read-only snapshot adds RPC42 selected fan stage to v3."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from raw_registers_v3 import parse_raw_v3
from snapshot_contract import SnapshotError

VERSION = 4


def make_v4(v3: dict, *, fan_level: int | None) -> dict:
    """Keep all 17 RPC45 readings; an unavailable RPC42 is null, not zero."""
    if type(fan_level) is not int and fan_level is not None:
        raise SnapshotError("Invalid fan level")
    if fan_level is not None and not 0 <= fan_level <= 4:
        raise SnapshotError("Invalid fan level")
    result = {**v3, "schema_version": VERSION, "fan_level": fan_level}
    parse_v4(result, expected_device_id=v3["device_id"])
    return result


def parse_v4(payload: Any, *, expected_device_id: str,
             now: datetime | None = None):
    if (type(payload) is not dict
            or set(payload) != {
                "schema_version", "device_id", "timestamp_utc", "health",
                "values", "raw_values", "optional", "fan_level",
            }
            or type(payload["schema_version"]) is not int
            or payload["schema_version"] != VERSION):
        raise SnapshotError("Invalid v4 snapshot")
    level = payload["fan_level"]
    if level is not None and (type(level) is not int or not 0 <= level <= 4):
        raise SnapshotError("Invalid selected fan level")
    v3 = {k: v for k, v in payload.items() if k not in ("fan_level", "schema_version")}
    v3["schema_version"] = 3
    base, raw = parse_raw_v3(v3, expected_device_id=expected_device_id, now=now)
    return base, raw, level
