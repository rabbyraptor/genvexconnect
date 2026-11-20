#!/usr/bin/env python3
"""Read-only Steam Deck gate before an *independently approved* diagnostic App start.

Never prints Supervisor options, passwords, tokens or private data.
The script does not change App settings, start containers or run Nabto RPC.
"""
from __future__ import annotations

import json
import subprocess
import sys

HOST = "root@rabbyshome.duckdns.org"
SSH = ("ssh", "-T", "-p", "22222", "-o", "BatchMode=yes", HOST)
APP = "local_genvex_nabto_remote"
DATA = "/mnt/data/supervisor/apps/data/local_genvex_nabto_remote"
FIELDS = ("device_id", "identity", "unlock_secret", "ipc_token")


def run_remote(command: str) -> str:
    completed = subprocess.run(
        [*SSH, command], capture_output=True, text=True, timeout=45, check=False
    )
    if completed.returncode:
        raise RuntimeError("Remote read-only check failed")
    if len(completed.stdout) > 262144:
        raise RuntimeError("Supervisor returned oversized metadata")
    return completed.stdout


def parse_info(raw: str) -> dict:
    doc = json.loads(raw)
    if not isinstance(doc, dict) or doc.get("result") != "ok":
        raise ValueError("Unexpected Supervisor response")
    data = doc.get("data")
    if not isinstance(data, dict):
        raise ValueError("Supervisor data absent")
    if (data.get("version"), data.get("state"), data.get("boot")) != (
        "0.1.0-dev2", "stopped", "manual"
    ):
        raise ValueError("App not stopped/manual/dev2")
    opts = data.get("options")
    if not isinstance(opts, dict):
        raise ValueError("Supervisor did not supply options")
    if any(key not in opts or opts[key] != "" for key in FIELDS):
        raise ValueError("Diagnostic requires all four credential fields empty")
    if type(opts.get("diagnostic_only")) is not bool:
        raise ValueError("Diagnostic option is not a boolean")
    if opts.get("diagnostic_only") is not False:
        raise ValueError("Expected baseline diagnostic_only=false")
    if type(opts.get("poll_seconds")) is not int or not 60 <= opts["poll_seconds"] <= 3600:
        raise ValueError("Unexpected poll interval")
    return {"poll_seconds": opts["poll_seconds"]}


def main(argv: list[str]) -> int:
    if argv == ["--preflight"]:
        print("===== DEV2 DIAGNOSTIC READ-ONLY PREFLIGHT =====")
        print("No App options, private bytes or credentials are printed.")
        print("No settings changes, start, stop or Nabto RPC.")
        print("PASS: inert preflight")
        return 0
    if argv != ["--execute-readonly"]:
        print("Usage: python3 audit_haos_dev2_diagnostic_prestart_from_deck_v1.py --preflight|--execute-readonly", file=sys.stderr)
        return 2

    print("===== DEV2 DIAGNOSTIC PRESTART GATE (READ ONLY) =====")
    try:
        info = parse_info(run_remote(f"ha apps info {APP} --raw-json"))
        print("PASS: installed dev2 stopped/manual; diagnostic disabled")
        print("PASS: all four Supervisor credential options confirmed empty")
        # Only metadata existence tests, not inspection/read of directory contents.
        # Exact known Supervisor path, no secret filenames or data emitted.
        command = (
            "sh -c '"
            "d=/mnt/data/supervisor/apps/data/local_genvex_nabto_remote; "
            "test -d \"$d\" && test ! -L \"$d\" || exit 8; "
            "for p in \"$d/profile\" \"$d/ipc-token\"; do "
            "test ! -e \"$p\" && test ! -L \"$p\" || exit 9; "
            "done; "
            "echo PRIVATE_PATHS_ABSENT'"
        )
        if run_remote(command).strip() != "PRIVATE_PATHS_ABSENT":
            raise RuntimeError("Private-path status unexpected")
        print("PASS: private profile and token paths absent (metadata-only)")
        # No Docker container may be in the running state.
        docker = (
            "sh -c '"
            "if docker inspect --type container app_local_genvex_nabto_remote "
            ">/dev/null 2>&1; then "
            "test \"$(docker inspect --type container app_local_genvex_nabto_remote "
            "--format \'{{.State.Running}}\')\" = false || exit 7; "
            "fi; echo REMOTE_APP_STOPPED'"
        )
        if run_remote(docker).strip() != "REMOTE_APP_STOPPED":
            raise RuntimeError("App container status unexpected")
        print("PASS: dedicated App container not running")
        print("INFO: poll_seconds baseline verified (value not displayed)")
        print("PASS: read-only gate; no changes to App or HAOS")
        print("===== DEV2 DIAGNOSTIC PRESTART GATE COMPLETE =====")
        return 0
    except (RuntimeError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired):
        print("BLOCKED: one or more diagnostic safety prerequisites not met")
        print("No App changes, start or stop attempted")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
