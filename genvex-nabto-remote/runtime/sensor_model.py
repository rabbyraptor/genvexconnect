"""Transport-independent, read-only Optima 270 sensor mapping.

This module deliberately imports no Home Assistant or legacy Nabto SDK code.
Only validated *live* RPC 45 batch values should enter decode_readings().
"""
from dataclasses import dataclass
from math import isfinite
from typing import Sequence

@dataclass(frozen=True)
class SensorSpec:
    key: str
    name: str
    address: int
    unit: str
    divisor: int
    offset: int
    device_class: str
    state_class: str = "measurement"

SENSORS = (
    SensorSpec("supply_air", "Supply air", 20, "°C", 10, -300, "temperature"),
    SensorSpec("outdoor_air", "Outdoor air", 21, "°C", 10, -300, "temperature"),
    SensorSpec("exhaust_air", "Exhaust air", 22, "°C", 10, -300, "temperature"),
    SensorSpec("extract_air", "Extract air", 23, "°C", 10, -300, "temperature"),
    SensorSpec("humidity", "Humidity", 26, "%", 1, 0, "humidity"),
)

class InvalidBatch(ValueError):
    """An RPC 45 result is missing, malformed or not the expected batch."""


def remote_hostname(device_id: str) -> str:
    """Construct hostname only from a verified 12-digit decimal ID."""
    if not isinstance(device_id, str) or len(device_id) != 12 or not device_id.isascii() or not device_id.isdecimal():
        raise ValueError("Device ID must be 12 ASCII decimal digits")
    return f"{device_id}.remote.lscontrol.dk"


def decode_readings(raw_values: Sequence[int]) -> dict[str, float]:
    """Decode five ordered signed int16 results; never return partial updates."""
    if not isinstance(raw_values, (list, tuple)) or len(raw_values) != len(SENSORS):
        raise InvalidBatch("RPC 45 requires five ordered values")
    decoded = {}
    for raw, spec in zip(raw_values, SENSORS):
        if type(raw) is not int or not -32768 <= raw <= 32767:
            raise InvalidBatch("Invalid signed int16 value")
        value = (raw + spec.offset) / spec.divisor
        if not isfinite(value):
            raise InvalidBatch("Non-finite sensor value")
        decoded[spec.key] = value
    return decoded
