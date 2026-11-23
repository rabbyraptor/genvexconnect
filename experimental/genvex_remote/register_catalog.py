"""Canonical DEV9 Optima 270 registers and source-audited Micro Nabto commands.

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


# Protocol opcodes are distinct from register addresses. The five opcodes below
# are the entire *currently identified* set, not the vendor's complete protocol.
# Source-derived writes are descriptive only: this module does not implement
# packet encoding, network access, or transmission.
@dataclass(frozen=True)
class MicroCommand:
    opcode: int
    name: str
    operation: str
    request: str
    response: str
    source: str
    evidence: str
    remote_verified: bool
    transmit_enabled: bool = False


MICRO_COMMANDS = (
    MicroCommand(2, "KEEP_ALIVE", "session",
                 "community LAN keep-alive payload", "source-only response",
                 "superrob/genvexnabto protocol/payload.py", "community_source_only", False),
    MicroCommand(17, "PING", "identify",
                 "ping.json gateway identity request",
                 "Pong, Devicenumber, Model, Version, SlaveDevicenumber, SlaveModel",
                 "Nabto LS Controls ping interface and remote evidence", "remote_verified", True),
    MicroCommand(42, "SETPOINT_READLIST", "read_setpoint",
                 "SDK: uint8 obj + uint16 address; source LAN packet format differs",
                 "SDK: prefix_unknown uint8 + list of uint16 values",
                 "RPC42 DEV9 and community readlist", "remote_verified_single_address_7", True),
    MicroCommand(43, "SETPOINT_WRITELIST", "write_setpoint",
                 "community LAN: uint8 obj + uint32 write_address + uint16 raw",
                 "remote response not verified; SDK write schema unknown",
                 "community writelist only", "community_source_only_unverified", False),
    MicroCommand(45, "DATAPOINT_READLIST", "read_datapoint",
                 "SDK: uint8 obj + uint32 address",
                 "SDK: ordered signed int16 values",
                 "RPC45 DEV9 and community readlist", "remote_verified_17_raw", True),
)
MICRO_COMMAND_BY_ID = {command.opcode: command for command in MICRO_COMMANDS}
MICRO_COMMAND_BY_NAME = {command.name: command for command in MICRO_COMMANDS}


@dataclass(frozen=True)
class SetpointDefinition:
    key: str
    label: str
    read_object: int
    read_address: int
    write_object: int
    write_address: int
    divisor: int
    offset: int
    raw_min: int
    raw_max: int
    step: float
    default_read: bool
    evidence: str
    remote_read_verified: bool
    remote_write_verified: bool = False
    write_enabled: bool = False

    def display_value(self, raw: int) -> float:
        """Source-model display formula only; not a remote write operation."""
        if type(raw) is not int or not self.raw_min <= raw <= self.raw_max:
            raise ValueError("Raw setpoint outside source-model range")
        return (raw + self.offset) / self.divisor


@dataclass(frozen=True)
class InactiveSetpoint:
    key: str
    read_address: int
    write_address: int
    reason: str
    status: str = "commented_out_in_source"


@dataclass(frozen=True)
class ModelProfile:
    model_key: str
    model_name: str
    source: str
    rpc45: tuple[RPC45Register, ...]
    setpoints: tuple[SetpointDefinition, ...]
    inactive_setpoints: tuple[InactiveSetpoint, ...]
    # Community-model identity hint, not a verified remote identity mapping.
    identity_hint: tuple[int, int] | None = None


# Optima 270 source-derived read AND write address pairs. The only verified
# remote RPC42 read in this model is fan_speed at object 0 / address 7.
# RPC43 write-address entries exist for documentation and future research;
# remote RPC43 behavior and all write permissions remain unverified.
OPTIMA270_SETPOINTS = (
    SetpointDefinition("fan_speed", "Ventilatortrin", 0, 7,
                       0, 24, 1, 0,
                       0, 4, 1, True,
                       "community_source_and_live_remote_rpc42", True),
    SetpointDefinition("temp_setpoint", "Temperatursetpunkt", 0, 1,
                       0, 12, 10, 100,
                       0, 200, 0.5, True,
                       "public_optima270_model_only", False),
    SetpointDefinition("bypass_openoffset", "Bypass åbneoffset (EE1)", 0, 21,
                       0, 52, 10, 0,
                       10, 100, 0.1, True,
                       "public_optima270_model_only", False),
    SetpointDefinition("bypass_turnoff", "Bypass slukgrænse (EE2)", 0, 29,
                       0, 68, 1, 0,
                       0, 20, 1, True,
                       "public_optima270_model_only", False),
    SetpointDefinition("bypass_force_speed", "Bypass tvangshastighed (EE3)", 0, 57,
                       0, 124, 1, 0,
                       0, 100, 1, True,
                       "public_optima270_model_only", False),
    SetpointDefinition("bypass_force_temp", "Bypass tvangstemperatur (EE4)", 0, 58,
                       0, 126, 10, 0,
                       0, 50, 0.1, True,
                       "public_optima270_model_only", False),
    SetpointDefinition("reheating", "Eftervarme (A1)", 0, 3,
                       0, 16, 1, 0,
                       0, 1, 1, True,
                       "public_optima270_model_only", False),
    SetpointDefinition("humidity_control", "Fugtstyring (A2)", 0, 6,
                       0, 22, 1, 0,
                       0, 1, 1, True,
                       "public_optima270_model_only", False),
    SetpointDefinition("boost_enable", "Boost aktiveret", 0, 30,
                       0, 70, 1, 0,
                       0, 1, 1, True,
                       "public_optima270_model_only", False),
    SetpointDefinition("boost_time", "Boostvarighed (A3)", 0, 70,
                       0, 150, 1, 0,
                       1, 120, 1, True,
                       "public_optima270_model_only", False),
    SetpointDefinition("filter_days", "Filterdage", 0, 100,
                       0, 210, 1, 0,
                       0, 65535, 1, True,
                       "public_optima270_model_only", False),
    SetpointDefinition("filter_reset", "Filterreset", 0, 50,
                       0, 110, 1, 0,
                       0, 2, 1, False,
                       "public_optima270_model_only", False),
)
OPTIMA270_INACTIVE_SETPOINTS = (
    InactiveSetpoint("bypass_min_on", 59, 128,
                     "Source comments: seems locked down"),
    InactiveSetpoint("supply_air_level1", 10, 30,
                     "Source comments: gateway write locked"),
    InactiveSetpoint("supply_air_level2", 11, 32,
                     "Source comments: gateway write locked"),
    InactiveSetpoint("supply_air_level3", 12, 34,
                     "Source comments: gateway write locked"),
    InactiveSetpoint("supply_air_level4", 8, 26,
                     "Source comments: gateway write locked"),
    InactiveSetpoint("extract_air_level1", 13, 36,
                     "Source comments: gateway write locked"),
    InactiveSetpoint("extract_air_level2", 14, 38,
                     "Source comments: gateway write locked"),
    InactiveSetpoint("extract_air_level3", 15, 40,
                     "Source comments: gateway write locked"),
    InactiveSetpoint("extract_air_level4", 9, 28,
                     "Source comments: gateway write locked"),
)
MODEL_PROFILES = {
    "optima270": ModelProfile(
        "optima270",
        "Genvex Optima 270",
        "https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/models/optima270.py",
        RPC45_ALL, OPTIMA270_SETPOINTS, OPTIMA270_INACTIVE_SETPOINTS,
        identity_hint=(79265, 2010),
    ),
}


def get_micro_command(opcode_or_name: int | str) -> MicroCommand:
    """Look up an identified operation, without creating a request."""
    command = (
        MICRO_COMMAND_BY_ID.get(opcode_or_name)
        if type(opcode_or_name) is int else
        MICRO_COMMAND_BY_NAME.get(opcode_or_name)
        if type(opcode_or_name) is str else None
    )
    if command is None:
        raise KeyError("Unknown Micro Nabto command")
    return command


def get_model(model_key: str) -> ModelProfile:
    """Explicit model lookup; do not guess a profile from device identity."""
    if type(model_key) is not str or model_key not in MODEL_PROFILES:
        raise KeyError("Unknown Nabto model profile")
    return MODEL_PROFILES[model_key]


def get_model_register(
    model_key: str, opcode: int, address: int, *, object_id: int = 0,
    include_inactive: bool = False,
) -> RPC45Register | SetpointDefinition | InactiveSetpoint:
    """Resolve an address in its opcode namespace; never perform I/O.

    RPC45 returns datapoint metadata. RPC42 uses *read* addresses and
    RPC43 uses *write* addresses, which are generally different. Inactive
    source-only settings require explicit opt-in to be visible.
    """
    model = get_model(model_key)
    if type(opcode) is not int or type(address) is not int or type(object_id) is not int:
        raise KeyError("Invalid command or register address")
    if opcode == 45:
        for item in model.rpc45:
            if object_id == 0 and item.address == address:
                return item
    elif opcode in (42, 43):
        for item in model.setpoints:
            obj = item.read_object if opcode == 42 else item.write_object
            addr = item.read_address if opcode == 42 else item.write_address
            if obj == object_id and addr == address:
                return item
        if include_inactive and object_id == 0:
            for item in model.inactive_setpoints:
                addr = item.read_address if opcode == 42 else item.write_address
                if addr == address:
                    return item
    raise KeyError("No register defined for model, opcode, object and address")


def get_model_setpoint(model_key: str, key: str) -> SetpointDefinition:
    """Find an active source-model setpoint by stable key."""
    for item in get_model(model_key).setpoints:
        if item.key == key:
            return item
    raise KeyError("Unknown active setpoint")


def _validate_protocol_library() -> None:
    if len(MICRO_COMMAND_BY_ID) != len(MICRO_COMMANDS):
        raise RuntimeError("Duplicate command opcode")
    if len(MICRO_COMMAND_BY_NAME) != len(MICRO_COMMANDS):
        raise RuntimeError("Duplicate command name")
    for model in MODEL_PROFILES.values():
        if len({item.key for item in model.setpoints}) != len(model.setpoints):
            raise RuntimeError("Duplicate setpoint key")
        if len({(item.read_object, item.read_address) for item in model.setpoints}) != len(model.setpoints):
            raise RuntimeError("Duplicate active setpoint read address")
        if len({(item.write_object, item.write_address) for item in model.setpoints}) != len(model.setpoints):
            raise RuntimeError("Duplicate active setpoint write address")
        for item in model.setpoints:
            if not item.divisor or not item.raw_min <= item.raw_max:
                raise RuntimeError("Invalid setpoint conversion or bounds")
            if item.write_enabled or item.remote_write_verified:
                raise RuntimeError("Unverified write capability must not be enabled")
    fan = get_model_setpoint("optima270", "fan_speed")
    if (fan.read_object, fan.read_address, fan.raw_min, fan.raw_max) != (
        RPC42_FAN_LEVEL.object_id, RPC42_FAN_LEVEL.address,
        RPC42_FAN_LEVEL.minimum, RPC42_FAN_LEVEL.maximum,
    ):
        raise RuntimeError("RPC42 fan-stage contract drift")


_validate_protocol_library()
