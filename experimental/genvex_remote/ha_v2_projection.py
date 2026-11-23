"""Offline-only Home Assistant projection for the proposed Optima270 v2 payload.

No Home Assistant imports, network, RPC calls, registration or device writes.
This is a reference contract, not an installed integration or live entity map.
Existing five v1 sensor keys/unique IDs remain unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from snapshot_v2_draft import parse_v2


@dataclass(frozen=True)
class SensorProjection:
    key: str
    name: str
    unit: str
    device_class: str | None
    state_class: str
    value: float | None
    available: bool

    def unique_id(self, device_id: str) -> str:
        """Match v1's `<device_id>_<key>` identity rule."""
        return f"{device_id}_{self.key}"


_BASE_FIELDS = (
    ("supply_air", "Supply air", "°C", "temperature"),
    ("outdoor_air", "Outdoor air", "°C", "temperature"),
    ("exhaust_air", "Exhaust air", "°C", "temperature"),
    ("extract_air", "Extract air", "°C", "temperature"),
    ("humidity", "Humidity", "%", "humidity"),
)

_OPTIONAL_FIELDS = (
    ("fan_duty_supply", "Supply fan", "%", None),
    ("fan_duty_extract", "Extract fan", "%", None),
)


def project_v2_sensors(
    payload: Any, *, expected_device_id: str, now: datetime | None = None,
    include_fan_duty: bool = False,
) -> tuple[SensorProjection, ...]:
    """Build a fresh deterministic HA-oriented view, no side effects.

    v2 parser fails closed on baseline errors; absence of optional *pair*
    gives unavailable fan entities (value None), never fabricated zeroes.
    No entities for unverified RPM/bypass/alarm/rotor semantics.
    The caller can request a v1-compatible five-sensor projection without
    registering optional fan-duty entities before live UI verification.
    """
    if type(include_fan_duty) is not bool:
        raise ValueError("Fan duty projection gate must be boolean")
    baseline, fans = parse_v2(
        payload, expected_device_id=expected_device_id, now=now
    )
    rows = [
        SensorProjection(key, name, unit, device_class, "measurement",
                         baseline[key], True)
        for key, name, unit, device_class in _BASE_FIELDS
    ]
    if include_fan_duty:
        rows.extend(
            SensorProjection(key, name, unit, device_class, "measurement",
                             fans.get(key), key in fans)
            for key, name, unit, device_class in _OPTIONAL_FIELDS
        )
    return tuple(rows)
