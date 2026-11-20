#!/usr/bin/env python3
"""Development-only, single-shot read-only RPC45 runner.

Not wired into the Supervisor App entrypoint. Requires an explicit operator
invocation in a separately reviewed live test. Never accepts credentials in
argv, environment or a file; one JSON line is supplied on stdin.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from app_bootstrap import validate_private_profile
from sdk_snapshot_adapter import SDKSnapshotAdapter, SDKSnapshotError
from sensor_model import remote_hostname
from snapshot_contract import parse_snapshot

PROFILE = Path("/data/profile")
PROBE = Path("/opt/genvex-remote/runtime/probe_remote_snapshot.py")
MAX_INPUT = 4096


def read_settings() -> dict:
    line = sys.stdin.buffer.readline(MAX_INPUT + 1)
    if not line or len(line) > MAX_INPUT or not line.endswith(b"\n"):
        raise ValueError("Invalid settings input")
    # Require EOF; prevent accidentally feeding additional commands/secrets.
    if sys.stdin.buffer.read(1):
        raise ValueError("Unexpected additional input")
    data = json.loads(line)
    if not isinstance(data, dict) or set(data) != {
        "device_id", "identity", "unlock_secret"
    }:
        raise ValueError("Unexpected settings schema")
    device_id = data["device_id"]
    remote_hostname(device_id)
    for key in ("identity", "unlock_secret"):
        value = data[key]
        if (not isinstance(value, str) or not 1 <= len(value) <= 1024
                or any(c in value for c in "\r\n\x00")):
            raise ValueError("Invalid setting")
    return data


async def read_once(settings: dict) -> None:
    adapter = SDKSnapshotAdapter(
        device_id=settings["device_id"],
        identity=settings["identity"],
        unlock_secret=settings["unlock_secret"],
        profile_dir=str(PROFILE),
        probe_file=str(PROBE),
        timeout_seconds=85,
    )
    result = await adapter.poll_once()
    parse_snapshot(result, expected_device_id=settings["device_id"])
    # No raw sensor values, secrets, URLs or SDK diagnostics in stdout.
    print("PASS: one read-only RPC45 snapshot validated", flush=True)


def main() -> int:
    try:
        settings = read_settings()
    except Exception:
        print("BLOCKED: INPUT_INVALID", flush=True)
        return 1
    try:
        validate_private_profile(PROFILE)
    except Exception:
        print("BLOCKED: PROFILE_INVALID", flush=True)
        return 1
    if not PROBE.is_file():
        print("BLOCKED: PROBE_MISSING", flush=True)
        return 1
    try:
        asyncio.run(read_once(settings))
        return 0
    except SDKSnapshotError as exc:
        # Strictly allowlisted code, not an exception message from SDK/QEMU.
        print("BLOCKED: " + exc.code, flush=True)
        return 1
    except Exception:
        print("BLOCKED: SNAPSHOT_OR_ADAPTER_INVALID", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
