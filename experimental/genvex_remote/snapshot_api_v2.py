"""Optional authenticated v2 read-only HTTP handler; no sockets or SDK.

Called only by an explicitly enabled, separately injected v2 snapshot provider.
v1 routing and payload contract remain untouched.
"""
from __future__ import annotations

import json
from typing import Any

from ipc_auth import IPCAuthError, authorize_read
from snapshot_contract import SnapshotError
from snapshot_v2_draft import parse_v2

V2_PATH = "/v2/snapshot"
_UNAVAILABLE = b'{"error":"unavailable"}'


def handle_v2_read_request(
    *, method: str, path: str, authorization: str | None,
    expected_token: str, device_id: str, snapshot: Any,
) -> tuple[int, bytes]:
    """Authenticate before route or provider access; never echo raw inputs."""
    try:
        if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
            raise IPCAuthError("Unauthorized")
        authorize_read(expected_token, authorization[len("Bearer "):])
    except IPCAuthError:
        return 401, b'{"error":"unauthorized"}'

    if method != "GET" or path != V2_PATH:
        return 404, b'{"error":"not_found"}'

    try:
        baseline, fans = parse_v2(snapshot, expected_device_id=device_id)
    except (ValueError, TypeError, SnapshotError):
        return 503, _UNAVAILABLE

    # Rebuild the envelope from validated, strictly allowlisted fields;
    # never forward the provider's opaque or secret-bearing data.
    result = {
        "schema_version": 2,
        "device_id": device_id,
        "timestamp_utc": snapshot["timestamp_utc"],
        "health": "ok",
        "values": baseline,
        "optional": {"fan_duty": fans},
    }
    return 200, json.dumps(
        result, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
