"""Versioned read-only Genvex Remote Home Assistant entity catalog."""
from __future__ import annotations

from dataclasses import dataclass

DOMAIN = "genvex_remote"
CONF_DEVICE_ID = "device_id"
CONF_RUNTIME_ENDPOINT = "runtime_endpoint"
CONF_RUNTIME_TOKEN = "runtime_token"
CONF_PAIR_FROM_APP = "pair_from_app"
CONF_RAW_REGISTERS_V3 = "raw_registers_v3"
CONF_FAN_LEVEL_V4 = "fan_level_v4"
POLL_SECONDS = 60

@dataclass(frozen=True)
class RemoteSensor:
    key: str
    translation_key: str
    address: int
    unit: str

SENSORS = (
    RemoteSensor("supply_air", "supply_air", 20, "°C"),
    RemoteSensor("outdoor_air", "outdoor_air", 21, "°C"),
    RemoteSensor("exhaust_air", "exhaust_air", 22, "°C"),
    RemoteSensor("extract_air", "extract_air", 23, "°C"),
    RemoteSensor("humidity", "humidity", 26, "%"),
)

@dataclass(frozen=True)
class RemoteRawRegister:
    key: str
    address: int
    label: str


# Exact RPC45 address map from archived authenticated read results.
# Values are raw signed int16, not inferred °C, %, RPM or alarms.
RAW_REGISTERS = (
    RemoteRawRegister("supply_air", 20, "Tilluft"),
    RemoteRawRegister("outdoor_air", 21, "Udeluft"),
    RemoteRawRegister("exhaust_air", 22, "Afkastluft"),
    RemoteRawRegister("extract_air", 23, "Fraluft"),
    RemoteRawRegister("humidity", 26, "Luftfugtighed"),
    RemoteRawRegister("frost_protection_temp", 24, "Frostbeskyttelse"),
    RemoteRawRegister("fan_duty_supply", 18, "Tilluftventilator styresignal"),
    RemoteRawRegister("fan_duty_extract", 19, "Fraluftventilator styresignal"),
    RemoteRawRegister("fan_rpm_supply", 35, "Tilluftventilator"),
    RemoteRawRegister("fan_rpm_extract", 36, "Fraluftventilator"),
    RemoteRawRegister("preheat_pwm", 41, "Forvarme"),
    RemoteRawRegister("reheat_pwm", 42, "Eftervarme"),
    RemoteRawRegister("bypass_active_raw", 53, "Bypassstatus"),
    RemoteRawRegister("bypass_analog_raw", 40, "Bypass analog"),
    RemoteRawRegister("alarm_word_1_raw", 114, "Alarmregister 1"),
    RemoteRawRegister("alarm_word_2_raw", 115, "Alarmregister 2"),
    RemoteRawRegister("rotor_rpm", 50, "Rotor"),
)


def valid_device_id(value: object) -> bool:
    """Reject non-ASCII, extra characters and non-string IDs."""
    return isinstance(value, str) and len(value) == 12 and value.isascii() and value.isdecimal()
