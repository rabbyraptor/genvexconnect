#!/usr/bin/env python3
"""Manual one-RPC45 plus private loopback IPC smoke test (no HAOS changes).

Credentials arrive only via stdin. Exactly one remote RPC45 attempt is made.
Then the resulting five-value snapshot is served only on container-local
127.0.0.1 with a fresh in-memory token, tested and immediately destroyed.
No background polling or Supervisor App modification.
"""
from __future__ import annotations

import asyncio
import http.client
import json
import secrets

from app_bootstrap import validate_private_profile
from live_once import PROFILE, PROBE, read_settings
from polling_http_server import SnapshotHTTPServer
from sdk_snapshot_adapter import SDKSnapshotAdapter, SDKSnapshotError
from snapshot_contract import parse_snapshot


def verify_loopback(port: int, token: str, state: dict) -> None:
    """Real local TCP connection; token never leaves the Docker container."""
    def fetch(header: str | None) -> tuple[int, bytes]:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        try:
            headers = {} if header is None else {"Authorization": header}
            connection.request("GET", "/v1/snapshot", headers=headers)
            response = connection.getresponse()
            return response.status, response.read(4097)
        finally:
            connection.close()

    status, body = fetch(None)
    if status != 401 or body != b'{"error":"unauthorized"}':
        raise ValueError("Unauthorized IPC contract failed")
    status, body = fetch("Bearer " + token)
    if status != 200:
        raise ValueError("Authenticated IPC contract failed")
    result = json.loads(body)
    parse_snapshot(result, expected_device_id=state["device_id"])
    if result["values"] != state["values"]:
        raise ValueError("Snapshot IPC mismatch")
    state.clear()
    status, body = fetch("Bearer " + token)
    if status != 503 or body != b'{"error":"unavailable"}':
        raise ValueError("Stale IPC snapshot was not invalidated")


async def one_shot_ipc_test(settings: dict) -> None:
    """Never retry or start a poller; destroy the listener after checks."""
    adapter = SDKSnapshotAdapter(
        device_id=settings["device_id"],
        identity=settings["identity"],
        unlock_secret=settings["unlock_secret"],
        profile_dir=str(PROFILE),
        probe_file=str(PROBE),
        timeout_seconds=85,
    )
    snapshot = await adapter.poll_once()
    parse_snapshot(snapshot, expected_device_id=settings["device_id"])
    token = secrets.token_urlsafe(32)
    state = {
        "schema_version": 1,
        "device_id": settings["device_id"],
        "timestamp_utc": snapshot["timestamp_utc"],
        "health": "ok",
        "values": dict(snapshot["values"]),
    }
    server = SnapshotHTTPServer(
        bind_host="127.0.0.1", port=0, token=token,
        device_id=settings["device_id"],
        snapshot_provider=lambda: state if state else None,
    )
    try:
        server.start()
        port = server._server.server_address[1]
        await asyncio.to_thread(verify_loopback, port, token, state)
    finally:
        state.clear()
        server.stop()


def main() -> int:
    try:
        settings = read_settings()
        validate_private_profile(PROFILE)
        if not PROBE.is_file():
            raise ValueError("Probe missing")
    except Exception:
        print("BLOCKED: IPC_ONCE_INPUT_OR_PROFILE_INVALID", flush=True)
        return 1
    try:
        asyncio.run(one_shot_ipc_test(settings))
    except SDKSnapshotError as error:
        print("BLOCKED: " + error.code, flush=True)
        return 1
    except Exception:
        print("BLOCKED: IPC_ONCE_FAILED", flush=True)
        return 1
    print("PASS: one RPC45 snapshot validated; private loopback IPC 401/200/503 verified", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
