#!/usr/bin/env python3
"""Read-only Gate P.5: installed DEV4, previous source and Supervisor backup.

No options, tokens, device identity or sensor readings printed. Intended to
run as root on HAOS, staged next to dev4_source_baseline_preflight.py.
No service start/stop and no configuration mutation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from dev4_source_baseline_preflight import verify_source_tree, SOURCE

APP = "local_genvex_nabto_remote"
BACKUP_SOURCE = SOURCE.parent / ".genvex-remote-dev3-source-backup"
HA_DIR = Path("/mnt/data/supervisor/homeassistant")
ID_SIGNATURE = "2be9240972de0a9d"
PREVIOUS_BACKUP_DATE = datetime.fromisoformat("2026-11-20T23:14:57+00:00")


class GateError(Exception):
    pass


def command_json(args: list[str], *, timeout: int = 40) -> dict:
    try:
        proc = subprocess.run(
            args, stdin=subprocess.DEVNULL, capture_output=True,
            text=True, timeout=timeout,
        )
        if proc.returncode:
            raise GateError("COMMAND_FAILED")
        raw = json.loads(proc.stdout)
        if type(raw) is not dict or raw.get("result") not in ("ok", None):
            raise GateError("INVALID_RESPONSE")
        if type(raw.get("data")) is not dict:
            raise GateError("INVALID_DATA")
        return raw["data"]
    except (ValueError, subprocess.TimeoutExpired, OSError):
        raise GateError("COMMAND_UNAVAILABLE") from None


def require(value: bool, code: str) -> None:
    if not value:
        raise GateError(code)
    print(code + ": PASS", flush=True)


def metadata_date(item: dict) -> datetime | None:
    raw = item.get("date")
    if type(raw) is not str:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (TypeError, ValueError):
        return None


def included_app(detail: dict) -> bool:
    apps = detail.get("apps", detail.get("addons", []))
    if type(apps) is not list:
        return False
    return any(
        (item.get("slug") if type(item) is dict else item) == APP
        for item in apps
    )


def find_backup(items: list, detail_reader) -> tuple[str, str] | None:
    eligible = []
    for row in items:
        if type(row) is not dict:
            continue
        slug = row.get("slug")
        date = metadata_date(row)
        if (type(slug) is str and re.fullmatch(r"[a-zA-Z0-9_-]{6,80}", slug)
                and date is not None and date > PREVIOUS_BACKUP_DATE):
            eligible.append((date, slug))
    for date, slug in sorted(eligible, reverse=True)[:12]:
        try:
            details = detail_reader(slug)
        except GateError:
            continue
        if included_app(details) and details.get("type") in ("partial", "full"):
            return slug, date.isoformat()
    return None


def check_ha_registry() -> None:
    entries = json.loads((HA_DIR / ".storage/core.config_entries").read_text())["data"]["entries"]
    registry = json.loads((HA_DIR / ".storage/core.entity_registry").read_text())["data"]["entities"]
    active = [e for e in entries
              if e.get("domain") == "genvex_remote"
              and e.get("disabled_by") is None]
    require(len(active) == 1, "HA_CONFIG_ENTRY")
    ids = sorted(e["entity_id"] for e in registry
                 if e.get("platform") == "genvex_remote")
    require(len(ids) == 5, "HA_FIVE_ENTITIES")
    digest = hashlib.sha256("\n".join(ids).encode()).hexdigest()[:16]
    require(digest == ID_SIGNATURE, "HA_ENTITY_IDS_UNCHANGED")


def main() -> int:
    if sys.argv[1:] != ["--execute-readonly"]:
        return 2
    print("===== DEV4 GATE P.5 POST-INSTALL VERIFICATION =====", flush=True)
    try:
        info = command_json(["ha", "apps", "info", APP, "--raw-json"])
        require(info.get("version") == "0.1.0-dev4", "DEV4_VERSION")
        require(info.get("state") == "stopped", "APP_STOPPED")
        require(info.get("boot") == "manual", "APP_MANUAL_BOOT")
        options = info.get("options", {})
        require(type(options) is dict and options.get("persistent_session", False) is False,
                "PERSISTENT_MODE_DISABLED")
        require(SOURCE.is_dir() and not SOURCE.is_symlink() and
                b'version: "0.1.0-dev4"' in (SOURCE / "config.yaml").read_bytes().splitlines(),
                "DEV4_SOURCE_PRESENT")
        require(all((SOURCE / name).is_file()
                    for name in (
                        "runtime/persistent_sdk_adapter.py",
                        "runtime/persistent_rpc45_worker.py",
                        "runtime/polling_runtime.py",
                    )), "PERSISTENT_WORKER_INSTALLED")
        count = verify_source_tree(BACKUP_SOURCE)
        require(count == 23, "DEV3_SOURCE_BACKUP_VERIFIED")
        check_ha_registry()
        list_data = command_json(["ha", "backups", "list", "--raw-json"])
        items = list_data.get("backups")
        require(type(items) is list, "SUPERVISOR_BACKUP_LIST")
        found = find_backup(
            items,
            lambda slug: command_json(
                ["ha", "backups", "info", slug, "--raw-json"], timeout=45
            ),
        )
        require(found is not None, "SUPERVISOR_DEV3_APP_BACKUP")
        slug, date = found
        print("BACKUP_ID:", slug)
        print("BACKUP_DATE_UTC:", date)
        print("BACKUPS_IN_INVENTORY:", len(items))
        print("GATE_P5_RESULT: PASS")
        return 0
    except GateError as exc:
        print("GATE_P5_RESULT: BLOCKED")
        print("ERROR_CATEGORY:", exc.args[0] if exc.args else "INVALID")
        return 1
    except Exception as exc:
        print("GATE_P5_RESULT: BLOCKED")
        print("ERROR_CATEGORY:", type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
