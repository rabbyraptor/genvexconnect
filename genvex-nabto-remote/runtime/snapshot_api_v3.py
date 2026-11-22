"""DEV8.3 authenticated versioned read-only raw register endpoint.

Uses the existing fixed private IPC bearer token, strict device matching
and bounded fields. No SDK call is initiated by an HTTP request.
"""
from __future__ import annotations

import json
from typing import Any

from ipc_auth import IPCAuthError, authorize_read
from raw_registers_v3 import BASE_KEYS, OPTIONAL_KEYS, parse_raw_v3

V3_PATH = "/v3/snapshot"


def handle_v3_read_request(
    *, method: str, path: str, authorization: str | None,
    expected_token: str, device_id: str, snapshot: Any,
) -> tuple[int, bytes]:
    """Authenticate first, then allow exactly one fixed read-only route."""
    try:
        if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
            raise IPCAuthError("Unauthorized")
        authorize_read(expected_token, authorization[len("Bearer "):])
    except IPCAuthError:
        return 401, b'{"error":"unauthorized"}'

    if method != "GET" or path != V3_PATH:
        return 404, b'{"error":"not_found"}'
    try:
        baseline, raw = parse_raw_v3(snapshot, expected_device_id=device_id)
    except (ValueError, TypeError):
        return 503, b'{"error":"unavailable"}'

    result = {
        "schema_version": 3,
        "device_id": device_id,
        "timestamp_utc": snapshot["timestamp_utc"],
        "health": "ok",
        "values": baseline,
        "raw_values": {key: raw[key] for key in BASE_KEYS},
        "optional": {"raw_registers": {
            key: raw[key] for key in OPTIONAL_KEYS if key in raw
        }},
    }
    return 200, json.dumps(
        result, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
