"""DEV9.1: explicit evidence metadata for already-readable RPC45 raw values.

This is presentation-only. It never issues RPC requests, changes sensor
states or claims that source model labels establish physical sensor hardware.
Five baseline readings have validated scaled HA measurements; two fan command
registers have a source formula and an official UI match at fan level 3;
the other ten remain unverified source-model interpretations.
"""
from __future__ import annotations

BASELINE = (20, 21, 22, 23, 26)
FAN_CONTROL_CANDIDATES = (18, 19)
RAW_ONLY = (24, 35, 36, 41, 42, 53, 40, 114, 115, 50)
ADDRESSES = BASELINE + (24,) + FAN_CONTROL_CANDIDATES + (
    35, 36, 41, 42, 53, 40, 114, 115, 50,
)
if len(ADDRESSES) != 17 or len(set(ADDRESSES)) != 17:
    raise RuntimeError("Invalid evidence catalog")

# Source names are only hints about meaning; no remote hardware discovery.
NOTES = {
    24: "Frost-sensor presence unverified; raw 0 does not prove -30 C.",
    35: ("Source labels fan RPM; Optima 270 documents RPM feedback in EB10, "
         "but this register needs two-speed and official UI comparison."),
    36: ("Source labels fan RPM; Optima 270 documents RPM feedback in EB10, "
         "but this register needs two-speed and official UI comparison."),
    41: "Source labels preheat PWM; raw 0 does not prove heating hardware.",
    42: "Source labels reheat PWM; RPC45 address 42 is not RPC42.",
    53: "Source labels bypass status; raw 0 is not verified as closed.",
    40: "Source labels bypass analog; physical scale remains unknown.",
    114: "Undecoded alarm bitfield; raw 0 is not an alarm-free verdict.",
    115: "Undecoded alarm bitfield; raw 0 is not an alarm-free verdict.",
    50: ("Source labels rotor speed; installed rotor hardware is unconfirmed. "
         "The controller menu Rotorstatus is a separate 0-4 state, "
         "so raw 10 must not be decoded as Rotorstatus."),
}


def raw_register_attributes(address: int, raw_value: int | None) -> dict:
    """Describe evidence without modifying a raw int16 sensor's native state.

    Only source display math for the two fan *control commands* is exposed,
    validated against official Genvex Connect UI at fan level 3.
    That number is not measured fan RPM/airflow or known EB9 mode.
    Missing optional data never yields a synthetic candidate value.
    """
    if type(address) is not int or address not in ADDRESSES:
        raise ValueError("Unknown RPC45 register")
    if raw_value is not None and (
        type(raw_value) is not int or not -32768 <= raw_value <= 32767
    ):
        raise ValueError("Invalid raw signed int16")

    attrs = {
        "rpc45_address": address,
        "raw_value_format": "signed_int16",
        "rpc45_readability": "live_verified",
    }
    if address in BASELINE:
        attrs["meaning_evidence"] = "validated_scaled_measurement"
    elif address in FAN_CONTROL_CANDIDATES:
        attrs["meaning_evidence"] = "source_model_official_ui_match"
        attrs["source_display_formula"] = "raw / 100"
        attrs["source_display_unit_candidate"] = "%"
        attrs["source_display_unit_verified_against_ui"] = True
        attrs["source_display_verified"] = True
        attrs["controller_eb9_fan_mode"] = "unknown"
        attrs["physical_airflow_verified"] = False
        attrs["interpretation_note"] = (
            "Source formula raw/100 matches official Genvex Connect fan display "
            "at level 3 (75% supply and 73% extract on 2026-11-22 23:36 CET); "
            "this is not measured airflow or RPM. EB9 mode remains unknown."
        )
        if raw_value is not None:
            attrs["source_display_value_candidate"] = round(raw_value / 100, 2)
    else:
        attrs["meaning_evidence"] = "source_model_only"
        attrs["interpretation_note"] = NOTES[address]
    return attrs
