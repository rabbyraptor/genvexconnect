"""Strict HA-side raw RPC45 v3 parser; no Home Assistant runtime imports."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .const import RAW_REGISTERS, SENSORS
from .snapshot import InvalidSnapshot, validate_snapshot

BASE = tuple(spec.key for spec in SENSORS)
ALL = tuple(spec.key for spec in RAW_REGISTERS)
EXTRA = ALL[len(BASE):]
if (
    tuple(spec.address for spec in RAW_REGISTERS)
    != (20, 21, 22, 23, 26, 24, 18, 19, 35, 36, 41, 42, 53, 40, 114, 115, 50)
    or len(ALL) != 17 or len(set(ALL)) != 17
):
    raise RuntimeError("Invalid raw RPC45 address map")


def _check_raw(values: object, keys: tuple[str, ...],
               *, optional: bool = False) -> dict[str, int]:
    if type(values) is not dict:
        raise InvalidSnapshot("Malformed raw register payload")
    if optional and not values:
        return {}
    if set(values) != set(keys):
        raise InvalidSnapshot("Incomplete raw register group")
    if any(type(value) is not int or not -32768 <= value <= 32767
           for value in values.values()):
        raise InvalidSnapshot("Invalid raw signed int16")
    return {key: values[key] for key in keys}


def validate_raw_v3(
    payload: Any, *, expected_device_id: str, now: datetime | None = None,
) -> tuple[dict[str, float], dict[str, int]]:
    """Validate scaled existing baseline and all actually sampled raw keys."""
    if type(payload) is not dict or set(payload) != {
        "schema_version", "device_id", "timestamp_utc", "health",
        "values", "raw_values", "optional",
    } or type(payload["schema_version"]) is not int or payload["schema_version"] != 3:
        raise InvalidSnapshot("Invalid v3 snapshot schema")
    baseline = validate_snapshot(
        {
            "schema_version": 1,
            "device_id": payload["device_id"],
            "timestamp_utc": payload["timestamp_utc"],
            "health": payload["health"],
            "values": payload["values"],
        },
        expected_device_id=expected_device_id, now=now,
    )
    raw_baseline = _check_raw(payload["raw_values"], BASE)
    opt = payload["optional"]
    if type(opt) is not dict or set(opt) != {"raw_registers"}:
        raise InvalidSnapshot("Malformed optional raw group")
    raw_extra = _check_raw(opt["raw_registers"], EXTRA, optional=True)
    for spec in SENSORS:
        raw = raw_baseline[spec.key]
        expected = float(raw if spec.key == "humidity" else (raw - 300) / 10)
        if abs(baseline[spec.key] - expected) > 1e-6:
            raise InvalidSnapshot("Inconsistent raw baseline")
    return baseline, raw_baseline | raw_extra
