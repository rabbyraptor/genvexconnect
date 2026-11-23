"""2B: source-grounded, OFFLINE-ONLY model lookup from sanitized ping metadata.

No Nabto SDK, networking, Home Assistant entity changes or live device reads.
The one rule below comes from superrob/genvexnabto's model adapter; it is
NOT yet validated against a live sanitized remote ping from this gateway.
Only return profiles whose remote read-only datapoints are verified.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from capability_catalog import ControllerProfile, OPTIMA_270


class UnknownModel(ValueError):
    """Malformed or unsupported source-derived controller identity."""


@dataclass(frozen=True)
class DeviceMetadata:
    """Strict, non-secret numeric subset of LS Control ping.json's response."""

    model: int
    device_number: int
    version: int
    slave_device_number: int
    slave_model: int


_NUMERIC_FIELDS = {
    "Model": "model",
    "Devicenumber": "device_number",
    "Version": "version",
    "SlaveDevicenumber": "slave_device_number",
    "SlaveModel": "slave_model",
}


def parse_numeric_ping(response: Mapping[str, Any]) -> DeviceMetadata:
    """Project an authentic ping response to whitelisted uint32 fields only.

    An untrusted response may include 'UserNames:' or other personal fields.
    This function neither reads nor copies them into the returned identity.
    An outer JSON RPC document must supply its already-extracted 'response'
    object here, after validating the transport/session separately.
    """
    if not isinstance(response, Mapping):
        raise UnknownModel("Invalid model metadata")
    clean: dict[str, int] = {}
    for rpc_field, python_field in _NUMERIC_FIELDS.items():
        raw = response.get(rpc_field)
        if type(raw) is not int or not 0 <= raw <= 0xFFFFFFFF:
            raise UnknownModel("Invalid model metadata")
        clean[python_field] = raw
    return DeviceMetadata(**clean)


def select_verified_remote_profile(metadata: DeviceMetadata) -> ControllerProfile:
    """Select only the remotely verified catalog (not every LAN model).

    Source: GenvexNabtoModelAdapter.translateToModel(model, deviceNumber,
    slaveDeviceNumber, slaveDeviceModel) for Optima 270.
    """
    if not isinstance(metadata, DeviceMetadata):
        raise UnknownModel("Invalid model metadata")
    if metadata.model == 2010 and metadata.device_number == 79265:
        return OPTIMA_270
    raise UnknownModel("No verified Remote profile for this model")


def planned_verified_reads(response: Mapping[str, Any]) -> tuple[tuple[int, int], ...]:
    """Plan known, verified RPC45 items; does not send a request."""
    metadata = parse_numeric_ping(response)
    profile = select_verified_remote_profile(metadata)
    return profile.read_addresses
