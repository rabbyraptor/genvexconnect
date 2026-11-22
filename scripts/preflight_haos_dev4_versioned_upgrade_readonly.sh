#!/usr/bin/env bash
# Read-only preflight for a future versioned DEV4 -> new candidate upgrade.
# Transfers no credentials; prints only normalized Supervisor/runtime metadata.
set -euo pipefail
umask 077
OUT=$(mktemp)
trap 'rm -f -- "$OUT"' EXIT
if ssh -T -p 22222 root@rabbyshome.duckdns.org 'python3 -' >"$OUT" 2>&1 <<'PY'
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

SLUG = "local_genvex_nabto_remote"
CONTAINER = "app_local_genvex_nabto_remote"
APP_SOURCE = Path("/mnt/data/supervisor/apps/local/genvex_nabto_remote")
PARENT = APP_SOURCE.parent

def capture(argv: list[str], timeout: int = 40) -> tuple[int, str]:
    result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, timeout=timeout)
    return result.returncode, result.stdout

def supervisor_data(argv: list[str]) -> dict:
    status, raw = capture(argv)
    if status:
        raise ValueError("SUPERVISOR_COMMAND_FAILED")
    payload = json.loads(raw)
    data = payload.get("data")
    if type(data) is not dict:
        raise ValueError("SUPERVISOR_FORMAT_INVALID")
    return data

print("===== DEV4 VERSIONED UPDATE PRE-FLIGHT =====")
try:
    info = supervisor_data(["ha", "apps", "info", SLUG, "--raw-json"])
    version = info.get("version")
    state = info.get("state")
    boot = info.get("boot")
    print("APP_VERSION:", version if isinstance(version, str) else "UNKNOWN")
    print("APP_STATE:", state if state in ("started", "stopped") else "UNKNOWN")
    print("APP_BOOT:", boot if boot in ("manual", "auto") else "UNKNOWN")
    print("UPDATE_AVAILABLE:", info.get("update_available") is True)
    options = info.get("options")
    if type(options) is dict:
        print("PERSISTENT_CONFIG:", options.get("persistent_session") is True)
        print("POLL_60S:", options.get("poll_seconds") == 60)
    else:
        print("OPTIONS: NOT_INCLUDED")

    code, raw = capture(["docker", "inspect", CONTAINER, "--format", "{{json .}}"])
    running = False
    if code == 0:
        inspection = json.loads(raw)
        running = inspection.get("State", {}).get("Running") is True
        ports = inspection.get("NetworkSettings", {}).get("Ports") or {}
        has_published_port = any(
            isinstance(bindings, list) and len(bindings) > 0
            for bindings in ports.values()
        )
        print("DOCKER_RUNNING:", running)
        print("HOST_PUBLISHED_PORT:", has_published_port)
    else:
        print("DOCKER_RUNNING: MISSING")
        has_published_port = True

    manifest = APP_SOURCE / "config.yaml"
    if not APP_SOURCE.is_dir() or APP_SOURCE.is_symlink() or manifest.is_symlink():
        print("APP_SOURCE: INVALID")
        raise SystemExit(2)
    source_text = manifest.read_text(encoding="utf-8")
    match = re.search(r'^version:\s*["\x27]?([\w.\-]+)', source_text, re.M)
    source_version = match.group(1) if match else None
    print("LOCAL_SOURCE_VERSION:", source_version or "UNKNOWN")

    stage_candidates = (
        PARENT / ".genvex-remote-dev4-source-stage",
        PARENT / ".genvex-remote-dev5-source-stage",
        PARENT / ".genvex-remote-dev4-source-backup",
    )
    occupied = [p.name for p in stage_candidates if p.exists() or p.is_symlink()]
    print("FUTURE_STAGE_OCCUPIED:", ",".join(occupied) if occupied else "none")
    print("AVAILABLE_SPACE_MIB:", shutil.disk_usage(PARENT).free // (1024**2))

    status, raw = capture(["ha", "backups", "list", "--raw-json"], timeout=60)
    if status == 0:
        try:
            items = json.loads(raw).get("data", {}).get("backups", [])
            print("BACKUP_INVENTORY_COUNT:", len(items) if type(items) is list else "UNKNOWN")
        except (ValueError, TypeError):
            print("BACKUP_INVENTORY: UNKNOWN_FORMAT")
    else:
        print("BACKUP_INVENTORY: UNAVAILABLE")

    metadata_ok = (
        version == "0.1.0-dev4"
        and boot == "manual"
        and state == "started"
        and running
        and source_version == "0.1.0-dev4"
        and not has_published_port
        and not occupied
        and shutil.disk_usage(PARENT).free >= 512*1024*1024
    )
    print("VERSIONED_UPDATE_PREFLIGHT:", "PASS" if metadata_ok else "BLOCKED")
    print("===== COMPLETE =====")
    raise SystemExit(0 if metadata_ok else 2)
except (ValueError, KeyError, TypeError, OSError, subprocess.TimeoutExpired):
    print("VERSIONED_UPDATE_PREFLIGHT: ERROR")
    print("===== COMPLETE =====")
    raise SystemExit(2)
PY
then
  RC=0
else
  RC=$?
fi
printf '\033[3J\033[2J\033[H'
cat "$OUT"
echo "EXIT_CODE: $RC"
exit "$RC"
