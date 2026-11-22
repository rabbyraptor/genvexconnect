"""DEV8.3 fixed Optima 270 raw RPC45 v3 snapshot contract.

v1 remains the deployed five-measurement contract. v2 remains a separate
seven-reading development draft. v3 adds all seventeen *raw* signed-int16
registers without asserting physical meaning for the twelve candidates.

Five baseline registers are required. The optional twelve-register read is
all-or-nothing: a failed secondary RPC leaves the five measurements valid
and the twelve raw candidates unavailable (never fabricated as zero).

This module contains no SDK, network I/O or Home Assistant imports.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from sensor_model import SENSORS, decode_readings, remote_hostname
from snapshot_contract import SnapshotError, parse_snapshot

VERSION = 3
BASE_REGISTERS = tuple((spec.key, spec.address) for spec in SENSORS)
OPTIONAL_REGISTERS = (
    ("frost_protection_temp", 24),
    ("fan_duty_supply", 18),
    ("fan_duty_extract", 19),
    ("fan_rpm_supply", 35),
    ("fan_rpm_extract", 36),
    ("preheat_pwm", 41),
    ("reheat_pwm", 42),
    ("bypass_active_raw", 53),
    ("bypass_analog_raw", 40),
    ("alarm_word_1_raw", 114),
    ("alarm_word_2_raw", 115),
    ("rotor_rpm", 50),
)
ALL_REGISTERS = BASE_REGISTERS + OPTIONAL_REGISTERS
BASE_KEYS = tuple(key for key, _ in BASE_REGISTERS)
OPTIONAL_KEYS = tuple(key for key, _ in OPTIONAL_REGISTERS)
ALL_KEYS = BASE_KEYS + OPTIONAL_KEYS
BASE_ADDRESSES = tuple(address for _, address in BASE_REGISTERS)
OPTIONAL_ADDRESSES = tuple(address for _, address in OPTIONAL_REGISTERS)
if (
    BASE_ADDRESSES != (20, 21, 22, 23, 26)
    or OPTIONAL_ADDRESSES != (24, 18, 19, 35, 36, 41, 42, 53, 40, 114, 115, 50)
    or len(set(ALL_KEYS)) != 17
    or len(set(BASE_ADDRESSES + OPTIONAL_ADDRESSES)) != 17
):
    raise RuntimeError("Unsafe raw register definition")


def _read_raw(values: object, *, keys: tuple[str, ...], optional: bool) -> dict[str, int]:
    if type(values) is not dict:
        raise SnapshotError("Malformed raw register data")
    if optional and not values:
        return {}
    if set(values) != set(keys):
        raise SnapshotError("Incomplete raw register group")
    if any(type(value) is not int or not -32768 <= value <= 32767
           for value in values.values()):
        raise SnapshotError("Malformed signed raw register")
    return {key: values[key] for key in keys}


def _as_raw_group(raw: Sequence[int] | None, keys: tuple[str, ...],
                  *, optional: bool) -> dict[str, int]:
    if raw is None and optional:
        return {}
    if type(raw) not in (tuple, list) or len(raw) != len(keys):
        raise SnapshotError("Malformed raw RPC45 batch")
    return _read_raw(dict(zip(keys, raw)), keys=keys, optional=optional)


def make_raw_v3(
    *, device_id: str, measured_at: datetime,
    baseline_raw: Sequence[int], additional_raw: Sequence[int] | None,
) -> dict[str, Any]:
    """Create one strict versioned document from two separately checked reads.

    The optional read must supply all twelve values; partial results are
    never silently accepted as a meaningful zero or partial group.
    """
    remote_hostname(device_id)
    if (
        type(measured_at) is not datetime
        or measured_at.tzinfo is None
        or measured_at.utcoffset() is None
    ):
        raise SnapshotError("Invalid measurement time")
    base = _as_raw_group(baseline_raw, BASE_KEYS, optional=False)
    additional = _as_raw_group(additional_raw, OPTIONAL_KEYS, optional=True)
    doc = {
        "schema_version": VERSION,
        "device_id": device_id,
        "timestamp_utc": measured_at.isoformat(),
        "health": "ok",
        "values": decode_readings(tuple(base[key] for key in BASE_KEYS)),
        "raw_values": base,
        "optional": {"raw_registers": additional},
    }
    parse_raw_v3(doc, expected_device_id=device_id, now=measured_at)
    return doc


def parse_raw_v3(
    payload: Any, *, expected_device_id: str,
    now: datetime | None = None,
) -> tuple[dict[str, float], dict[str, int]]:
    """Validate complete five-value baseline plus the optional raw group.

    Return baseline and only actually observed raw registers. If the second
    RPC failed, the returned raw mapping contains precisely the five
    baseline keys; never make zero-valued missing registers.
    """
    if type(payload) is not dict or set(payload) != {
        "schema_version", "device_id", "timestamp_utc", "health",
        "values", "raw_values", "optional",
    } or type(payload["schema_version"]) is not int or payload["schema_version"] != VERSION:
        raise SnapshotError("Invalid raw v3 snapshot schema")
    baseline = parse_snapshot({
        "schema_version": 1,
        "device_id": payload["device_id"],
        "timestamp_utc": payload["timestamp_utc"],
        "health": payload["health"],
        "values": payload["values"],
    }, expected_device_id=expected_device_id, now=now)
    raw_base = _read_raw(payload["raw_values"], keys=BASE_KEYS, optional=False)
    optional = payload["optional"]
    if type(optional) is not dict or set(optional) != {"raw_registers"}:
        raise SnapshotError("Invalid optional raw group")
    raw_extra = _read_raw(
        optional["raw_registers"], keys=OPTIONAL_KEYS, optional=True,
    )
    expected = decode_readings(tuple(raw_base[key] for key in BASE_KEYS))
    if any(abs(baseline[key] - expected[key]) > 1e-6 for key in BASE_KEYS):
        raise SnapshotError("Raw baseline disagrees with sensor data")
    return baseline, raw_base | raw_extra
