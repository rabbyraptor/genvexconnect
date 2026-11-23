"""Authenticated read-only v4 snapshot endpoint; no SDK in HTTP path."""
from __future__ import annotations

import json

from ipc_auth import IPCAuthError, authorize_read
from raw_snapshot_v4 import parse_v4

V4_PATH = "/v4/snapshot"


def handle_v4_read_request(*, method, path, authorization,
                           expected_token, device_id, snapshot):
    try:
        if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
            raise IPCAuthError("Unauthorized")
        authorize_read(expected_token, authorization[len("Bearer "):])
    except IPCAuthError:
        return 401, b'{"error":"unauthorized"}'
    if method != "GET" or path != V4_PATH:
        return 404, b'{"error":"not_found"}'
    try:
        _, _, _ = parse_v4(snapshot, expected_device_id=device_id)
    except (ValueError, TypeError):
        return 503, b'{"error":"unavailable"}'
    return 200, json.dumps(snapshot, separators=(",", ":"), allow_nan=False).encode()
