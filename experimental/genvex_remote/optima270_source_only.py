"""2B Optima 270: source-only, NOT REMOTE-VERIFIED candidate inventory.

Only the 12 addresses below are copied from the public Optima270 model's
read-only datapoint table. They are *not* included in capability_catalog.OPTIMA_270,
do not create HA entities, and must NEVER be sent by the normal read planner.

Source:
https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/models/optima270.py
"""
from __future__ import annotations

from dataclasses import dataclass

from capability_catalog import OPTIMA_270


class InvalidCandidate(ValueError):
    """A proposed source-only datapoint is not a valid declaration."""


@dataclass(frozen=True)
class SourceOnlyDatapoint:
    key: str
    label: str
    address: int
    scale_offset: int = 0
    scale_divisor: int = 1
    engineering_note: str = ""

    def __post_init__(self) -> None:
        if (
            not isinstance(self.key, str)
            or not self.key.isascii()
            or not self.key
            or any(not (c.islower() or c.isdigit() or c == "_") for c in self.key)
            or not isinstance(self.label, str)
            or not self.label.strip()
        ):
            raise InvalidCandidate("Invalid candidate identity")
        if type(self.address) is not int or not 0 <= self.address <= 0xFFFFFFFF:
            raise InvalidCandidate("Invalid candidate address")
        if (
            type(self.scale_offset) is not int
            or type(self.scale_divisor) is not int
            or self.scale_divisor <= 0
        ):
            raise InvalidCandidate("Invalid source scaling")
        if not isinstance(self.engineering_note, str):
            raise InvalidCandidate("Invalid engineering note")

    @property
    def object_id(self) -> int:
        """Upstream GenvexNabtoBaseModel supplies default obj=0."""
        return 0

    @property
    def remote_status(self) -> str:
        return "source_only_unverified"


# These 12 entries are *not* a scan range and are not live-read permissions.
# Source scales only: do NOT infer true percent/boolean/alarm semantics from
# numeric raw values without comparing with an authorized actual device.
OPTIMA_270_SOURCE_ONLY = (
    SourceOnlyDatapoint(
        "frost_protection_temp", "Frostbeskyttelsestemperatur", 24, -300, 10
    ),
    SourceOnlyDatapoint(
        "fan_duty_supply", "Tilluftventilator: styregrad", 18, 0, 100,
        "Kildevisning bruger %, men skalaens fysiske betydning skal kontrolleres."
    ),
    SourceOnlyDatapoint(
        "fan_duty_extract", "Fraluftventilator: styregrad", 19, 0, 100,
        "Kildevisning bruger %, men skalaens fysiske betydning skal kontrolleres."
    ),
    SourceOnlyDatapoint(
        "fan_rpm_supply", "Tilluftventilator: omdrejninger", 35
    ),
    SourceOnlyDatapoint(
        "fan_rpm_extract", "Fraluftventilator: omdrejninger", 36
    ),
    SourceOnlyDatapoint(
        "preheat_pwm", "Forvarme: PWM", 41, 0, 100,
        "Reguleringssignal; verificer den reelle skala før en HA %-entitet."
    ),
    SourceOnlyDatapoint(
        "reheat_pwm", "Eftervarme: PWM", 42, 0, 100,
        "Adresse 42 i RPC45 er IKKE kommando-ID RPC42."
    ),
    SourceOnlyDatapoint(
        "bypass_active_raw", "Bypass: rå aktivstatus", 53, 0, 1,
        "Boolsk 0/1-fortolkning er endnu ikke remote-verificeret."
    ),
    SourceOnlyDatapoint(
        "bypass_analog_raw", "Bypass: analog råværdi", 40, 0, 1,
        "Fysisk skalering/enhed ukendt."
    ),
    SourceOnlyDatapoint(
        "alarm_word_1_raw", "Alarmregister 1: råværdi", 114, 0, 1,
        "Rå bitfelt; fortolkning kræver særskilte alarmtest."
    ),
    SourceOnlyDatapoint(
        "alarm_word_2_raw", "Alarmregister 2: råværdi", 115, 0, 1,
        "Rå bitfelt; fortolkning kræver særskilte alarmtest."
    ),
    SourceOnlyDatapoint(
        "rotor_rpm", "Rotor: omdrejninger", 50, 0, 1,
        "Rotor kan mangle på nogle hardwarekonfigurationer."
    ),
)


def list_source_only_candidates() -> tuple[SourceOnlyDatapoint, ...]:
    """Offline inventory, NOT a network read plan."""
    verified_keys = {reading.key for reading in OPTIMA_270.readings}
    verified_addresses = {reading.address for reading in OPTIMA_270.readings}
    candidate_keys = [item.key for item in OPTIMA_270_SOURCE_ONLY]
    candidate_addresses = [item.address for item in OPTIMA_270_SOURCE_ONLY]
    if (
        len(set(candidate_keys)) != len(candidate_keys)
        or len(set(candidate_addresses)) != len(candidate_addresses)
        or verified_keys.intersection(candidate_keys)
        or verified_addresses.intersection(candidate_addresses)
    ):
        raise InvalidCandidate("Candidate inventory conflicts with verified values")
    return OPTIMA_270_SOURCE_ONLY
