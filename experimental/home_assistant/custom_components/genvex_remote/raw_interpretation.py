"""DEV9.1: explicit evidence metadata for already-readable RPC45 raw values.

This is presentation-only. It never issues RPC requests, changes sensor
states or claims that source model labels establish physical sensor hardware.
Five baseline readings have validated scaled HA measurements; two fan command
registers have a source formula and an official UI match at fan level 3;
the other ten remain unverified source-model interpretations.
"""
from __future__ import annotations

from .register_catalog import (
    RPC45_ALL, RPC45_BASELINE, RPC45_BY_ADDRESS, RPC45_OPTIONAL,
)

BASELINE = tuple(spec.address for spec in RPC45_BASELINE)
FAN_CONTROL_CANDIDATES = tuple(
    spec.address for spec in RPC45_OPTIONAL if spec.display_divisor is not None
)
RAW_ONLY = tuple(
    spec.address for spec in RPC45_OPTIONAL if spec.display_divisor is None
)
ADDRESSES = tuple(spec.address for spec in RPC45_ALL)
NOTES = {spec.address: spec.note for spec in RPC45_OPTIONAL if spec.note}


def raw_register_attributes(address: int, raw_value: int | None) -> dict:
    """Describe evidence without modifying a raw int16 sensor's native state.

    Only source display math for the two fan *control commands* is exposed,
    validated against official Genvex Connect UI at fan level 3.
    That number is not measured fan RPM/airflow or known EB9 mode.
    Missing optional data never yields a synthetic candidate value.
    """
    if type(address) is not int or address not in RPC45_BY_ADDRESS:
        raise ValueError("Unknown RPC45 register")
    if raw_value is not None and (
        type(raw_value) is not int or not -32768 <= raw_value <= 32767
    ):
        raise ValueError("Invalid raw signed int16")

    spec = RPC45_BY_ADDRESS[address]
    attrs = {
        "rpc45_address": address,
        "raw_value_format": "signed_int16",
        "rpc45_readability": "live_verified",
    }
    if address in BASELINE:
        attrs["meaning_evidence"] = spec.evidence
    elif address in FAN_CONTROL_CANDIDATES:
        attrs["meaning_evidence"] = spec.evidence
        attrs["source_display_formula"] = f"raw / {spec.display_divisor}"
        attrs["source_display_unit_candidate"] = "%"
        attrs["source_display_unit_verified_against_ui"] = True
        attrs["source_display_verified"] = True
        attrs["controller_eb9_fan_mode"] = "unknown"
        attrs["physical_airflow_verified"] = False
        attrs["interpretation_note"] = spec.note
        if raw_value is not None:
            attrs["source_display_value_candidate"] = round(raw_value / spec.display_divisor, 2)
    else:
        attrs["meaning_evidence"] = spec.evidence
        attrs["interpretation_note"] = spec.note
    return attrs
