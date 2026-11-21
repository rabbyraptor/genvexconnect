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
from sensor_model import SENSORS, remote_hostname
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


def format_readings(values: dict[str, float]) -> tuple[str, ...]:
    """Allowlisted five sensor values only, never raw SDK output or device ID."""
    return tuple(
        f"VALUE {spec.key}: {values[spec.key]:.{0 if spec.unit == '%' else 1}f} {spec.unit}"
        for spec in SENSORS
    )


async def read_once(settings: dict, *, show_values: bool = False) -> None:
    adapter = SDKSnapshotAdapter(
        device_id=settings["device_id"],
        identity=settings["identity"],
        unlock_secret=settings["unlock_secret"],
        profile_dir=str(PROFILE),
        probe_file=str(PROBE),
        timeout_seconds=85,
    )
    result = await adapter.poll_once()
    readings = parse_snapshot(result, expected_device_id=settings["device_id"])
    lines = format_readings(readings) if show_values else ()
    # Credentials, hostname, device ID and raw SDK output never reach stdout.
    print("PASS: one read-only RPC45 snapshot validated", flush=True)
    if show_values:
        print("READINGS_BEGIN", flush=True)
        for line in lines:
            print(line, flush=True)
        print("READINGS_END", flush=True)


def main() -> int:
    try:
        if sys.argv[1:] not in ([], ["--show-values"], ["--diagnose"]):
            raise ValueError("Unsupported display option")
        show_values = sys.argv[1:] == ["--show-values"]
        diagnose = sys.argv[1:] == ["--diagnose"]
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
        asyncio.run(read_once(settings, show_values=show_values))
        return 0
    except SDKSnapshotError as exc:
        # Strictly allowlisted code, not an exception message from SDK/QEMU.
        print("BLOCKED: " + exc.code, flush=True)
        if diagnose:
            # Never print raw stdout, exception text, URLs or credentials.
            # These are strictly bounded numeric markers from the SDK probe.
            status = exc.rpc_status if exc.rpc_status is not None else "unknown"
            elapsed = exc.elapsed_ms if exc.elapsed_ms is not None else "unknown"
            print(f"DIAG RPC45_STATUS: {status}", flush=True)
            print(f"DIAG RPC45_ELAPSED_MS: {elapsed}", flush=True)
        return 1
    except Exception:
        print("BLOCKED: SNAPSHOT_OR_ADAPTER_INVALID", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
