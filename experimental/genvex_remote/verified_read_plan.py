"""2B offline RPC45 request planner for *verified* Optima 270 readings ONLY.

Produces a pure, structured request body compatible with the existing,
previously validated read-only Nabto XML. Does not import Nabto SDK, create
URLs, open sessions, fetch candidate data or change Home Assistant.

Source-only candidates are deliberately NOT accepted here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from capability_catalog import ControllerProfile, OPTIMA_270
from model_lookup import parse_numeric_ping, select_verified_remote_profile


class UnsafeReadPlan(ValueError):
    """An unverified or malformed RPC45 plan was requested."""


@dataclass(frozen=True)
class Rpc45Plan:
    """Strictly ordered, source-grounded read-only request plan."""

    model_key: str
    semantic_keys: tuple[str, ...]
    datapoints: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        if (
            self.model_key != "optima270"
            or len(self.datapoints) != 5
            or len(self.semantic_keys) != len(self.datapoints)
            or len(set(self.datapoints)) != 5
            or len(set(self.semantic_keys)) != 5
            or any(type(obj) is not int or type(addr) is not int
                   or not 0 <= obj <= 255 or not 0 <= addr <= 0xFFFFFFFF
                   for obj, addr in self.datapoints)
        ):
            raise UnsafeReadPlan("Only the verified Optima270 five-item batch is allowed")

        # Do not allow untrusted callers to inject even a *validly formatted*
        # source-only, unknown or reordered address in the current v1 plan.
        if self.datapoints != OPTIMA_270.read_addresses or self.semantic_keys != tuple(
            reading.key for reading in OPTIMA_270.readings
        ):
            raise UnsafeReadPlan("Unverified RPC45 address or key")

    @property
    def rpc_id(self) -> int:
        return 45

    @property
    def query_name(self) -> str:
        return "candidate_read_datapoints.json"

    def request_body(self) -> dict[str, Any]:
        """Return an inert Python dict; NO SDK/network invocation occurs."""
        return {
            "request": {
                "datapoints": [
                    {"obj": obj, "address": address}
                    for obj, address in self.datapoints
                ],
                "trailer": 1,
            }
        }


def plan_current_verified_read(profile: ControllerProfile) -> Rpc45Plan:
    """Allow only canonical, remotely verified catalog entries."""
    if profile is not OPTIMA_270 or profile.read_rpc_id != 45:
        raise UnsafeReadPlan("Unsupported or unverified controller profile")
    if any(item.evidence != "remote_rpc45_verified" for item in profile.readings):
        raise UnsafeReadPlan("Source-only sensor cannot be requested")
    return Rpc45Plan(
        model_key=profile.model_key,
        semantic_keys=tuple(reading.key for reading in profile.readings),
        datapoints=profile.read_addresses,
    )


def plan_from_numeric_ping(ping_response: Mapping[str, Any]) -> Rpc45Plan:
    """Model metadata -> reviewed profile -> verified read-only five-item plan.

    Pass ONLY the already extracted 'response' mapping (not whole RPC JSON).
    Sensitive optional fields such as UserNames: are ignored by model_lookup.
    The result is a request description, not a device call.
    """
    return plan_current_verified_read(
        select_verified_remote_profile(parse_numeric_ping(ping_response))
    )
