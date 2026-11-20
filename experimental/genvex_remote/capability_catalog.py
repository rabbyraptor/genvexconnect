"""Offline-only read-only capability catalog prototype (maintenance plan 2A).

This file is deliberately outside both installable integration and HAOS App.
It models source-verified controller capabilities but does not discover devices,
open Nabto sessions, issue RPCs, or create Home Assistant entities.

Only Optima 270's five authenticated RPC45 readings are declared as remotely
verified. New models/addresses MUST have their own independent evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal, Sequence


ValueKind = Literal["number", "boolean", "enum"]
EntityDomain = Literal["sensor", "binary_sensor"]


class CatalogError(ValueError):
    """Invalid model, unsupported capability or malformed raw reading."""


@dataclass(frozen=True)
class Reading:
    """An immutable declaration of one read-only, source-grounded datapoint."""

    key: str
    label: str
    object_id: int
    address: int
    kind: ValueKind
    ha_platform: EntityDomain
    device_class: str | None
    unit: str | None = None
    scale_offset: int = 0
    scale_divisor: int = 1
    enum_options: tuple[tuple[int, str], ...] = ()
    evidence: str = "synthetic_only"

    def __post_init__(self) -> None:
        if not self.key or not self.key.isascii() or not all(
            c.islower() or c.isdigit() or c == "_" for c in self.key
        ):
            raise CatalogError("Invalid semantic key")
        if not self.label or not self.label.strip():
            raise CatalogError("Invalid label")
        if type(self.object_id) is not int or not 0 <= self.object_id <= 255:
            raise CatalogError("Invalid RPC object ID")
        if type(self.address) is not int or not 0 <= self.address <= 0xFFFFFFFF:
            raise CatalogError("Invalid RPC address")
        if self.kind not in ("number", "boolean", "enum"):
            raise CatalogError("Invalid capability type")
        if self.ha_platform not in ("sensor", "binary_sensor"):
            raise CatalogError("Invalid entity platform")
        if not isinstance(self.evidence, str) or not self.evidence:
            raise CatalogError("Capability provenance required")
        if self.kind == "number":
            if self.ha_platform != "sensor":
                raise CatalogError("Numeric values must use sensor platform")
            if type(self.scale_offset) is not int or type(self.scale_divisor) is not int or self.scale_divisor <= 0:
                raise CatalogError("Invalid numeric scale")
            if self.enum_options:
                raise CatalogError("Numeric sensor cannot declare enum options")
        else:
            if self.scale_offset != 0 or self.scale_divisor != 1 or self.unit is not None:
                raise CatalogError("Non-numeric capability cannot have numeric scaling")
            if self.kind == "boolean":
                if self.ha_platform != "binary_sensor" or self.enum_options:
                    raise CatalogError("Boolean must map to binary_sensor")
            elif self.ha_platform != "sensor" or not self.enum_options:
                raise CatalogError("Enum must map to sensor with known options")
            if self.kind == "enum":
                raw = [number for number, _ in self.enum_options]
                labels = [label for _, label in self.enum_options]
                if (any(type(v) is not int or not -32768 <= v <= 32767 for v in raw)
                        or len(set(raw)) != len(raw)
                        or any(not isinstance(label, str) or not label for label in labels)
                        or len(set(labels)) != len(labels)):
                    raise CatalogError("Invalid enum mapping")

    def decode(self, raw: int) -> float | bool | str:
        """Strict int16 decoding; unsupported statuses are never invented."""
        if type(raw) is not int or not -32768 <= raw <= 32767:
            raise CatalogError("Invalid raw signed int16 reading")
        if self.kind == "boolean":
            if raw not in (0, 1):
                raise CatalogError("Unexpected boolean value")
            return bool(raw)
        if self.kind == "enum":
            for value, label in self.enum_options:
                if value == raw:
                    return label
            raise CatalogError("Unknown enum value")
        decoded = (raw + self.scale_offset) / self.scale_divisor
        if not isfinite(decoded):
            raise CatalogError("Invalid numeric value")
        return float(decoded)


@dataclass(frozen=True)
class ControllerProfile:
    """Known query specification; never a claim of auto-enumeration."""

    model_key: str
    manufacturer: str
    model_name: str
    read_rpc_id: int
    readings: tuple[Reading, ...]
    capability_enumeration: Literal["unverified", "verified"] = "unverified"

    def __post_init__(self) -> None:
        if not self.model_key or not self.manufacturer or not self.model_name:
            raise CatalogError("Missing controller identity")
        if type(self.read_rpc_id) is not int or not 0 <= self.read_rpc_id <= 0xFFFFFFFF:
            raise CatalogError("Invalid read RPC")
        if not self.readings:
            raise CatalogError("A known profile must contain at least one reading")
        keys = [reading.key for reading in self.readings]
        addresses = [(reading.object_id, reading.address) for reading in self.readings]
        if len(keys) != len(set(keys)) or len(addresses) != len(set(addresses)):
            raise CatalogError("Duplicate semantic key or object/address")
        if self.capability_enumeration not in ("unverified", "verified"):
            raise CatalogError("Invalid enumeration evidence")

    @property
    def read_addresses(self) -> tuple[tuple[int, int], ...]:
        """Ordered, explicit (obj, address) pairs only; not a register scan."""
        return tuple((reading.object_id, reading.address) for reading in self.readings)

    def decode_batch(self, raw: Sequence[int]) -> dict[str, float | bool | str]:
        """All-or-nothing decoding, matching the existing snapshot v1 policy."""
        if not isinstance(raw, (list, tuple)) or len(raw) != len(self.readings):
            raise CatalogError("Incomplete read-only batch")
        return {reading.key: reading.decode(value) for reading, value in zip(self.readings, raw)}


# Sources: superrob/genvexnabto models/optima270.py (obj defaults to 0,
# address, divider, offset), plus the project's independently observed
# authenticated read-only remote RPC45 five-address batch (2026-11-19).
# Semantic keys MUST remain compatible with current snapshot contract v1.
OPTIMA_270 = ControllerProfile(
    model_key="optima270",
    manufacturer="Genvex",
    model_name="Optima 270",
    read_rpc_id=45,
    readings=(
        Reading("supply_air", "Supply air", 0, 20, "number", "sensor", "temperature",
                "°C", -300, 10, evidence="remote_rpc45_verified"),
        Reading("outdoor_air", "Outdoor air", 0, 21, "number", "sensor", "temperature",
                "°C", -300, 10, evidence="remote_rpc45_verified"),
        Reading("exhaust_air", "Exhaust air", 0, 22, "number", "sensor", "temperature",
                "°C", -300, 10, evidence="remote_rpc45_verified"),
        Reading("extract_air", "Extract air", 0, 23, "number", "sensor", "temperature",
                "°C", -300, 10, evidence="remote_rpc45_verified"),
        Reading("humidity", "Humidity", 0, 26, "number", "sensor", "humidity",
                "%", evidence="remote_rpc45_verified"),
    ),
)

PROFILES = (OPTIMA_270,)


def get_profile(model_key: str) -> ControllerProfile:
    """Explicit supported model selection; no guessed fallback address map."""
    if not isinstance(model_key, str):
        raise CatalogError("Unknown controller model")
    for profile in PROFILES:
        if profile.model_key == model_key:
            return profile
    raise CatalogError("Unknown controller model")
