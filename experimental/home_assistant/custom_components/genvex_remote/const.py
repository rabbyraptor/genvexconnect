"""Isolated future Home Assistant integration constants (not deployable yet)."""
from __future__ import annotations

from dataclasses import dataclass

DOMAIN = "genvex_remote"
CONF_DEVICE_ID = "device_id"
CONF_RUNTIME_ENDPOINT = "runtime_endpoint"
CONF_RUNTIME_TOKEN = "runtime_token"
CONF_PAIR_FROM_APP = "pair_from_app"
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

def valid_device_id(value: object) -> bool:
    """Reject non-ASCII, extra characters and non-string IDs."""
    return isinstance(value, str) and len(value) == 12 and value.isascii() and value.isdecimal()
