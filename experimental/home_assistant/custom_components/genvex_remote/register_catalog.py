"""Canonical, read-only DEV9 Optima 270 register *facts*.

This module is authored only at experimental/genvex_remote/register_catalog.py.
The App and HA copies are identical deployment projections, checked by
scripts/check_remote_runtime_parity.py. It contains no SDK or HA imports.

A source-model label is not evidence of installed physical hardware; raw
RPC45 states remain signed int16, not inferred physical measurements.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RPC45Register:
    key: str
    address: int
    label: str
    group: str
    name: str = ""
    unit: str = ""
    divisor: int = 1
    offset: int = 0
    device_class: str = ""
    evidence: str = "source_model_only"
    note: str = ""
    display_divisor: int | None = None


@dataclass(frozen=True)
class RPC42Read:
    object_id: int
    address: int
    minimum: int
    maximum: int


RPC42_FAN_LEVEL = RPC42Read(object_id=0, address=7, minimum=0, maximum=4)

RPC45_BASELINE = (
    RPC45Register("supply_air", 20, "Tilluft", "baseline",
                  "Supply air", "°C", 10, -300, "temperature",
                  "validated_scaled_measurement"),
    RPC45Register("outdoor_air", 21, "Udeluft", "baseline",
                  "Outdoor air", "°C", 10, -300, "temperature",
                  "validated_scaled_measurement"),
    RPC45Register("exhaust_air", 22, "Afkastluft", "baseline",
                  "Exhaust air", "°C", 10, -300, "temperature",
                  "validated_scaled_measurement"),
    RPC45Register("extract_air", 23, "Fraluft", "baseline",
                  "Extract air", "°C", 10, -300, "temperature",
                  "validated_scaled_measurement"),
    RPC45Register("humidity", 26, "Luftfugtighed", "baseline",
                  "Humidity", "%", 1, 0, "humidity",
                  "validated_scaled_measurement"),
)

_FAN_NOTE = (
    "Source formula raw/100 matches official Genvex Connect fan display "
    "at level 3 (75% supply and 73% extract on 2026-11-22 23:36 CET); "
    "this is not measured airflow or RPM. EB9 mode remains unknown."
)
RPC45_OPTIONAL = (
    RPC45Register("frost_protection_temp", 24, "Frostbeskyttelse", "optional",
                  note="Frost-sensor presence unverified; raw 0 does not prove -30 C."),
    RPC45Register("fan_duty_supply", 18, "Tilluftventilator styresignal",
                  "optional", evidence="source_model_official_ui_match",
                  note=_FAN_NOTE, display_divisor=100),
    RPC45Register("fan_duty_extract", 19, "Fraluftventilator styresignal",
                  "optional", evidence="source_model_official_ui_match",
                  note=_FAN_NOTE, display_divisor=100),
    RPC45Register("fan_rpm_supply", 35, "Tilluftventilator", "optional",
                  note=("Source labels fan RPM; Optima 270 documents RPM feedback "
                        "in EB10, but this register needs two-speed and official UI comparison.")),
    RPC45Register("fan_rpm_extract", 36, "Fraluftventilator", "optional",
                  note=("Source labels fan RPM; Optima 270 documents RPM feedback "
                        "in EB10, but this register needs two-speed and official UI comparison.")),
    RPC45Register("preheat_pwm", 41, "Forvarme", "optional",
                  note="Source labels preheat PWM; raw 0 does not prove heating hardware."),
    RPC45Register("reheat_pwm", 42, "Eftervarme", "optional",
                  note="Source labels reheat PWM; RPC45 address 42 is not RPC42."),
    RPC45Register("bypass_active_raw", 53, "Bypassstatus", "optional",
                  note="Source labels bypass status; raw 0 is not verified as closed."),
    RPC45Register("bypass_analog_raw", 40, "Bypass analog", "optional",
                  note="Source labels bypass analog; physical scale remains unknown."),
    RPC45Register("alarm_word_1_raw", 114, "Alarmregister 1", "optional",
                  note="Undecoded alarm bitfield; raw 0 is not an alarm-free verdict."),
    RPC45Register("alarm_word_2_raw", 115, "Alarmregister 2", "optional",
                  note="Undecoded alarm bitfield; raw 0 is not an alarm-free verdict."),
    RPC45Register("rotor_rpm", 50, "Rotor", "optional",
                  note=("Source labels rotor speed; installed rotor hardware is unconfirmed. "
                        "The controller menu Rotorstatus is a separate 0-4 state, "
                        "so raw 10 must not be decoded as Rotorstatus.")),
)
RPC45_ALL = RPC45_BASELINE + RPC45_OPTIONAL
RPC45_BY_ADDRESS = {spec.address: spec for spec in RPC45_ALL}

if (
    len(RPC45_BASELINE) != 5 or len(RPC45_OPTIONAL) != 12
    or len(RPC45_BY_ADDRESS) != 17
    or len({spec.key for spec in RPC45_ALL}) != 17
    or any(spec.divisor <= 0 for spec in RPC45_ALL)
):
    raise RuntimeError("Invalid canonical RPC45 catalog")
