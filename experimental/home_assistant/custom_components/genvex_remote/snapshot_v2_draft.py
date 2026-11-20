"""Experimental v2 snapshot parser for the *uninstalled* HA scaffold.

Does not modify the v1 integration, coordinator, entities or endpoint. This
pure parser validates the same five mandatory readings as v1 and an optional
complete fan-duty pair; never substitutes zero for missing fan data.
"""
from __future__ import annotations

from math import isfinite
from typing import Any
from datetime import datetime

from .snapshot import InvalidSnapshot, validate_snapshot

FAN_KEYS = frozenset({"fan_duty_supply", "fan_duty_extract"})


def validate_v2_snapshot(
    snapshot: Any, *, expected_device_id: str,
    now: datetime | None = None, max_age_seconds: int = 180,
) -> tuple[dict[str, float], dict[str, float]]:
    """Return a validated base and optional fan pair, never leaked metadata."""
    if type(snapshot) is not dict or set(snapshot) != {
        "schema_version", "device_id", "timestamp_utc", "health",
        "values", "optional",
    } or type(snapshot["schema_version"]) is not int or snapshot["schema_version"] != 2:
        raise InvalidSnapshot("Invalid v2 snapshot schema")
    base = validate_snapshot(
        {
            "schema_version": 1,
            "device_id": snapshot["device_id"],
            "timestamp_utc": snapshot["timestamp_utc"],
            "health": snapshot["health"],
            "values": snapshot["values"],
        },
        expected_device_id=expected_device_id, now=now,
        max_age_seconds=max_age_seconds,
    )
    optional = snapshot["optional"]
    if type(optional) is not dict or set(optional) != {"fan_duty"}:
        raise InvalidSnapshot("Invalid optional v2 fields")
    fans = optional["fan_duty"]
    if type(fans) is not dict or (fans and set(fans) != FAN_KEYS):
        raise InvalidSnapshot("Incomplete fan duty pair")
    validated: dict[str, float] = {}
    for key, value in fans.items():
        if type(value) not in (int, float) or not isfinite(value) or not 0 <= value <= 100:
            raise InvalidSnapshot("Invalid optional fan value")
        validated[key] = float(value)
    return base, validated
