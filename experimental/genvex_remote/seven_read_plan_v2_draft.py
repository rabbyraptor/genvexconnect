"""Inert seven-address read-only RPC45 plan for a future atomic v2 poll.

This module does not import or invoke the Nabto SDK, does not open a session
and is not wired into HAOS. The combined seven-address batch succeeded in one authorized read-only
RPC45 on Steam Deck (2026-11-20); this offline module itself performs no RPC.
That one-shot result does not prove HAOS/QEMU deployment or recurring polling.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from sensor_model import SENSORS, decode_readings, remote_hostname
from snapshot_contract import SnapshotError
from snapshot_v2_draft import make_v2_from_v1

RPC_ID = 45
ORDERED_ADDRESSES = tuple(s.address for s in SENSORS) + (18, 19)
ORDERED_KEYS = tuple(s.key for s in SENSORS) + (
    "fan_duty_supply", "fan_duty_extract",
)


def request_body() -> dict[str, Any]:
    """Construct exactly seven obj=0 source-backed datapoints, never a scan."""
    if ORDERED_ADDRESSES != (20, 21, 22, 23, 26, 18, 19):
        raise SnapshotError("Unexpected v2 RPC45 address list")
    return {
        "request": {
            "datapoints": [{"obj": 0, "address": a} for a in ORDERED_ADDRESSES],
            "trailer": 1,
        }
    }


def decode_seven_to_v2(
    raw: Sequence[int], *, device_id: str, measured_at: datetime,
) -> dict[str, Any]:
    """One complete ordered RPC response -> one timestamped v2 document.

    Invalid baseline or incomplete response rejects the whole snapshot.
    A well-formed but out-of-range optional fan pair becomes unavailable;
    it never contaminates the baseline or fabricates zeroes.
    """
    remote_hostname(device_id)
    if (
        not isinstance(measured_at, datetime)
        or measured_at.tzinfo is None
        or measured_at.utcoffset() is None
    ):
        raise SnapshotError("Measurement needs an aware timestamp")
    if type(raw) not in (list, tuple) or len(raw) != len(ORDERED_ADDRESSES):
        raise SnapshotError("Seven-item batch incomplete")
    if any(type(v) is not int or not -32768 <= v <= 32767 for v in raw):
        raise SnapshotError("Invalid signed int16 in seven-item batch")

    try:
        base = decode_readings(raw[:5])
    except ValueError as exc:
        raise SnapshotError("Invalid baseline readings") from exc

    timestamp = measured_at.astimezone(timezone.utc).isoformat()
    v1 = {
        "schema_version": 1, "device_id": device_id,
        "timestamp_utc": timestamp, "health": "ok", "values": base,
    }
    return make_v2_from_v1(
        v1, expected_device_id=device_id,
        fan_raw=raw[5:], now=measured_at,
    )
