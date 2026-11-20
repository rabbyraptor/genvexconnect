"""Pure read-only HTTP handler core for future authenticated internal IPC.

No socket listener or publicly accessible server is created by this module.
The future server adapter must enforce trusted networking, TLS as applicable,
per-install token provisioning, bounded request sizes and process isolation.
"""
from __future__ import annotations

import json
from typing import Any

from ipc_auth import IPCAuthError, authorize_read
from sensor_model import remote_hostname
from snapshot_contract import SnapshotError, parse_snapshot

_ALLOWED_PATH = "/v1/snapshot"


def handle_read_request(
    *, method: str, path: str, authorization: str | None,
    expected_token: str, device_id: str, snapshot: Any,
) -> tuple[int, bytes]:
    """Produce only status code and redacted safe body.

    Authentication precedes route disclosure. Do not expose raw RPC/SDK
    errors, credentials, internal profile paths or partial sensor results.
    """
    try:
        if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
            raise IPCAuthError("Unauthorized runtime request")
        supplied = authorization[len("Bearer "):]
        authorize_read(expected_token, supplied)
    except IPCAuthError:
        return 401, b'{"error":"unauthorized"}'

    if method != "GET" or path != _ALLOWED_PATH:
        return 404, b'{"error":"not_found"}'

    try:
        remote_hostname(device_id)
        readings = parse_snapshot(snapshot, expected_device_id=device_id)
    except (ValueError, SnapshotError):
        return 503, b'{"error":"unavailable"}'

    # Strictly project authorized and validated fields, never forward
    # arbitrary content from an SDK or another backend.
    result = {
        "schema_version": 1,
        "device_id": device_id,
        "timestamp_utc": snapshot["timestamp_utc"],
        "health": "ok",
        "values": readings,
    }
    return 200, json.dumps(result, separators=(",", ":"), allow_nan=False).encode("utf-8")
