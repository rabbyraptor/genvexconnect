"""Versioned read-only Genvex Remote Home Assistant entity catalog."""
from __future__ import annotations

from dataclasses import dataclass

from .register_catalog import RPC45_BASELINE, RPC45_ALL, rpc45_default_icon

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
    icon: str

SENSORS = tuple(
    RemoteSensor(spec.key, spec.key, spec.address, spec.unit, rpc45_default_icon(spec.key))
    for spec in RPC45_BASELINE
)

@dataclass(frozen=True)
class RemoteRawRegister:
    key: str
    address: int
    label: str
    icon: str


# Diagnostic names and addresses project the canonical register facts.
# This does not confer physical units or meaning upon raw signed int16 data.
RAW_REGISTERS = tuple(
    RemoteRawRegister(spec.key, spec.address, spec.label, rpc45_default_icon(spec.key))
    for spec in RPC45_ALL
)

def valid_device_id(value: object) -> bool:
    """Reject non-ASCII, extra characters and non-string IDs."""
    return isinstance(value, str) and len(value) == 12 and value.isascii() and value.isdecimal()
