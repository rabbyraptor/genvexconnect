"""Offline-only Optima270 snapshot v2 draft; v1 remains unchanged.

This is NOT an HAOS runtime API or a live Nabto planner. It describes a
future additive v2 payload with a complete v1 baseline and optional,
independently validated fan-duty readings. A failed optional read never
invalidates an otherwise fresh five-reading v1 baseline.
"""
from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any

from snapshot_contract import SnapshotError, parse_snapshot

V2_VERSION = 2
FAN_DUTY_ADDRESSES = {"fan_duty_supply": 18, "fan_duty_extract": 19}
FAN_DUTY_KEYS = frozenset(FAN_DUTY_ADDRESSES)


def decode_optional_fan_duty(raw: Any) -> dict[str, float]:
    """Decode an exact two-item RPC45 result or fail closed; no partial fan pair."""
    if type(raw) not in (list, tuple) or len(raw) != 2:
        raise SnapshotError("Optional fan duty batch incomplete")
    result = {}
    for key, value in zip(FAN_DUTY_ADDRESSES, raw):
        if type(value) is not int or not 0 <= value <= 10000:
            raise SnapshotError("Invalid optional fan duty raw value")
        result[key] = value / 100.0
    return result


def make_v2_from_v1(
    v1: Any, *, expected_device_id: str,
    fan_raw: Any = None, now: datetime | None = None,
) -> dict[str, Any]:
    """Produce an inert v2 document from a valid v1 baseline and optional fans.

    Caller must separately arrange an authorized read. This function performs
    NO I/O. Optional errors degrade to unavailable, never synthetic zeros.
    """
    baseline = parse_snapshot(v1, expected_device_id=expected_device_id, now=now)
    fans: dict[str, float] = {}
    if fan_raw is not None:
        try:
            fans = decode_optional_fan_duty(fan_raw)
        except SnapshotError:
            pass
    return {
        "schema_version": V2_VERSION,
        "device_id": expected_device_id,
        "timestamp_utc": v1["timestamp_utc"],
        "health": "ok",
        "values": baseline,
        "optional": {"fan_duty": fans},
    }


def parse_v2(
    payload: Any, *, expected_device_id: str,
    now: datetime | None = None,
) -> tuple[dict[str, float], dict[str, float]]:
    """Validate a v2 envelope; preserve the v1 five-reading safety contract."""
    if type(payload) is not dict or set(payload) != {
        "schema_version", "device_id", "timestamp_utc", "health", "values", "optional"
    } or type(payload["schema_version"]) is not int or payload["schema_version"] != V2_VERSION:
        raise SnapshotError("Unsupported v2 snapshot schema")
    baseline = parse_snapshot(
        {key: payload[key] for key in (
            "schema_version", "device_id", "timestamp_utc", "health", "values"
        )} | {"schema_version": 1},
        expected_device_id=expected_device_id, now=now,
    )
    optional = payload["optional"]
    if type(optional) is not dict or set(optional) != {"fan_duty"}:
        raise SnapshotError("Malformed optional section")
    fans = optional["fan_duty"]
    if type(fans) is not dict or (set(fans) != FAN_DUTY_KEYS and fans != {}):
        raise SnapshotError("Incomplete optional fan pair")
    for value in fans.values():
        if type(value) not in (int, float) or not isfinite(value) or not 0 <= value <= 100:
            raise SnapshotError("Invalid optional fan value")
    return baseline, {key: float(value) for key, value in fans.items()}
