#!/usr/bin/env python3
"""One real RPC45 snapshot served briefly on a private HAOS Docker bridge.

Manual operator-only executable, NOT an App entrypoint. Credentials and the
per-run bearer token arrive exclusively through one bounded stdin JSON line.
Makes one read-only RPC45 attempt, then serves the complete fresh snapshot
for up to 60 seconds over authenticated HTTP on the *container interface*.
The caller must use a private Docker bridge with NO published host port.
No periodic polling, retry, HA registry writes, or persistent state.
"""
from __future__ import annotations

import asyncio
import json
import sys

from app_bootstrap import validate_private_profile
from ipc_auth import authorize_read
from live_once import PROFILE, PROBE
from polling_http_server import SnapshotHTTPServer
from sdk_snapshot_adapter import SDKSnapshotAdapter, SDKSnapshotError
from sensor_model import remote_hostname
from snapshot_contract import parse_snapshot

MAX_INPUT = 4096
PORT = 18275
SERVE_SECONDS = 60


def read_settings() -> dict:
    line = sys.stdin.buffer.readline(MAX_INPUT + 1)
    if not line or len(line) > MAX_INPUT or not line.endswith(b"\n"):
        raise ValueError("Invalid input")
    if sys.stdin.buffer.read(1):
        raise ValueError("Unexpected trailing input")
    data = json.loads(line)
    if not isinstance(data, dict) or set(data) != {
        "device_id", "identity", "unlock_secret", "ipc_token",
    }:
        raise ValueError("Unexpected settings")
    remote_hostname(data["device_id"])
    for key in ("identity", "unlock_secret"):
        val = data[key]
        if (not isinstance(val, str) or not 1 <= len(val) <= 1024
                or any(char in val for char in "\r\n\x00")):
            raise ValueError("Invalid credentials")
    authorize_read(data["ipc_token"], data["ipc_token"])
    return data


async def serve_once(settings: dict, *, sleep=asyncio.sleep) -> None:
    """Exactly one SDK call, then authenticated HTTP with bounded lifetime."""
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

    state = {
        "schema_version": 1,
        "device_id": settings["device_id"],
        "timestamp_utc": snapshot["timestamp_utc"],
        "health": "ok",
        "values": dict(snapshot["values"]),
    }
    server = SnapshotHTTPServer(
        bind_host="0.0.0.0", port=PORT,
        token=settings["ipc_token"], device_id=settings["device_id"],
        snapshot_provider=lambda: state if state else None,
    )
    try:
        server.start()
        # No external acknowledgement or write endpoint is exposed.
        # The host operator terminates this disposable container as soon
        # as its one Core read verifies the snapshot.
        await sleep(SERVE_SECONDS)
    finally:
        state.clear()
        server.stop()


def main() -> int:
    if sys.argv[1:]:
        print("BLOCKED: INVALID_ARGUMENTS", flush=True)
        return 1
    try:
        settings = read_settings()
        validate_private_profile(PROFILE)
        if not PROBE.is_file():
            raise ValueError("Missing SDK probe")
    except Exception:
        print("BLOCKED: INPUT_OR_PROFILE_INVALID", flush=True)
        return 1
    try:
        asyncio.run(serve_once(settings))
    except SDKSnapshotError as err:
        print("BLOCKED: " + err.code, flush=True)
        return 1
    except Exception:
        print("BLOCKED: IPC_CORE_LIVE_ONCE_FAILED", flush=True)
        return 1
    print("PASS: one RPC45 snapshot service expired and stopped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
