#!/usr/bin/env python3
"""Read-only DEV5 post-install gate: Supervisor, exact source, backup, HA registry.

Executes on HAOS host, using only Python standard library and local ha/docker
commands. No App start/stop/update, SDK calls, credentials, raw options, or
sensor readings are displayed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

APP = "local_genvex_nabto_remote"
CONTAINER = "app_local_genvex_nabto_remote"
ROOT = Path("/mnt/data/supervisor/apps/local")
SOURCE = ROOT / "genvex_nabto_remote"
BACKUP_SOURCE = ROOT / ".genvex-remote-dev4-source-backup"
HA_DIR = Path("/mnt/data/supervisor/homeassistant")
BEFORE_BACKUP_COUNT = 8
AFTER_COMMIT_UTC = datetime.fromisoformat("2026-11-22T10:50:00+00:00")
# Git blob SHA-1 from tested source commit 65ba9cb79ca9785aee8eb760435b00926ac1a687.
# Source-only allowlist: three App files and seventeen runtime .py files.
EXPECTED = {
    "Dockerfile": "c91923037f1f879ef1b8ed8394f0046774ae002c",
    "config.yaml": "07be9932acf8cdac9e8c4a9d6482ecc5ab369d12",
    "run.sh": "d5384bb01bf93fa347d5fa61c3773a819c4cac44",
    "runtime/app_bootstrap.py": "acdbcfb548b7539c6e3075f49f3a074620abaa79",
    "runtime/diagnostic_http_server.py": "1fad502d212345beb7d5b42c18e34f382b88fc95",
    "runtime/ipc_auth.py": "78c0574f017b3987fc2e3b4ad792c040ebd4e88a",
    "runtime/offline_ipc_network_smoke.py": "6c70b7bd3944c9ebe757f05f5db53e0f5eb5a439",
    "runtime/persistent_rpc45_worker.py": "0400c2c41fce3e8c563a8c30d913472fd75a558c",
    "runtime/persistent_sdk_adapter.py": "62a2895437a1b8e6cda101d6b765b8fa30145158",
    "runtime/polling_http_server.py": "2c3533cf9674f8d7160e086e209696d75941e630",
    "runtime/polling_runtime.py": "2fe0d8ff39fe81d2f818415de3c0f989c94a6f8b",
    "runtime/polling_service.py": "039d108d22463ab73e9d65860a6c5383905d9d09",
    "runtime/polling_worker.py": "4860c08ebe8bde705f50271204efb3c2edc452b8",
    "runtime/probe_remote_snapshot.py": "31744afe87bad8eae349f695925ecacd0e455f6d",
    "runtime/profile_provision.py": "c36fcfe9e51d75ee3dc9ec2d6801dd776cd42173",
    "runtime/sdk_snapshot_adapter.py": "2b55624e31331596135eb7dc8068a39a932760f7",
    "runtime/sensor_model.py": "a2f1ee7fc363654b6320d1d707472566f90b889b",
    "runtime/snapshot_api.py": "054ad899b6132a1df4fc37a7862f9c47a1d23f91",
    "runtime/snapshot_contract.py": "e276b5d21ebd646138dbaf85ebc5527ece2bc974",
    "runtime/snapshot_state.py": "d1d5abe94318fcc7792e762b52805df854051e45",
}
UNCHANGED_DEV4 = {
    "runtime/app_bootstrap.py": EXPECTED["runtime/app_bootstrap.py"],
    "runtime/persistent_sdk_adapter.py": EXPECTED["runtime/persistent_sdk_adapter.py"],
    "runtime/polling_runtime.py": EXPECTED["runtime/polling_runtime.py"],
    "runtime/ipc_auth.py": EXPECTED["runtime/ipc_auth.py"],
    "runtime/sdk_snapshot_adapter.py": EXPECTED["runtime/sdk_snapshot_adapter.py"],
}


class GateBlocked(Exception):
    """Non-secret, bounded gate failure category."""


def require(test: bool, category: str) -> None:
    if not test:
        raise GateBlocked(category)
    print(category + ": PASS", flush=True)


def command_json(argv: list[str], timeout: int = 60) -> dict:
    try:
        result = subprocess.run(argv, capture_output=True, text=True,
                                stdin=subprocess.DEVNULL, timeout=timeout)
        if result.returncode:
            raise GateBlocked("HOST_COMMAND_FAILED")
        payload = json.loads(result.stdout)
        data = payload.get("data")
        if type(data) is not dict:
            raise GateBlocked("HOST_RESPONSE_INVALID")
        return data
    except (OSError, ValueError, subprocess.TimeoutExpired):
        raise GateBlocked("HOST_COMMAND_UNAVAILABLE") from None


def git_blob_sha(blob: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(blob)).encode("ascii") + b"\x00" + blob).hexdigest()


def inspect_source(path: Path, expected: dict[str, str], strict: bool) -> int:
    if not path.is_dir() or path.is_symlink():
        raise GateBlocked("SOURCE_DIRECTORY_INVALID")
    for rel, digest in expected.items():
        item = path / rel
        if item.is_symlink() or not item.is_file():
            raise GateBlocked("SOURCE_FILE_MISSING")
        if item.stat().st_size > 150_000:
            raise GateBlocked("SOURCE_FILE_TOO_LARGE")
        if git_blob_sha(item.read_bytes()) != digest:
            raise GateBlocked("SOURCE_HASH_MISMATCH")
    if strict:
        actual = set()
        for candidate in path.rglob("*"):
            if candidate.is_symlink():
                raise GateBlocked("SOURCE_SYMLINK")
            if candidate.is_file():
                actual.add(candidate.relative_to(path).as_posix())
        if actual != set(expected):
            raise GateBlocked("SOURCE_MEMBER_SET_MISMATCH")
    return len(expected)


def parse_date(text: object) -> datetime | None:
    if type(text) is not str:
        return None
    try:
        date = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if date.tzinfo is None:
            return None
        return date.astimezone(timezone.utc)
    except ValueError:
        return None


def backup_includes_app(detail: object) -> bool:
    if type(detail) is not dict or detail.get("type") not in ("partial", "full"):
        return False
    apps = detail.get("apps", detail.get("addons", []))
    if type(apps) is not list:
        return False
    for entry in apps:
        slug = entry.get("slug") if type(entry) is dict else entry
        if slug == APP:
            if type(entry) is dict and entry.get("version") not in (
                None, "0.1.0-dev4"
            ):
                continue
            return True
    return False


def find_new_backup(rows: object, read_detail) -> tuple[str, str] | None:
    if type(rows) is not list:
        raise GateBlocked("BACKUP_INVENTORY_INVALID")
    candidates = []
    for row in rows:
        if type(row) is not dict:
            continue
        slug = row.get("slug")
        date = parse_date(row.get("date"))
        if (type(slug) is str
                and re.fullmatch(r"[A-Za-z0-9_-]{6,80}", slug)
                and date is not None and date > AFTER_COMMIT_UTC):
            candidates.append((date, slug))
    for date, slug in sorted(candidates, reverse=True)[:12]:
        try:
            detail = read_detail(slug)
        except GateBlocked:
            continue
        if backup_includes_app(detail):
            return slug, date.isoformat()
    return None


def check_registry() -> None:
    # Inspect registry only: HA Core can be running while the App is stopped.
    try:
        records = json.loads(
            (HA_DIR / ".storage/core.config_entries").read_text()
        )["data"]["entries"]
        entities = json.loads(
            (HA_DIR / ".storage/core.entity_registry").read_text()
        )["data"]["entities"]
    except (OSError, ValueError, KeyError, TypeError):
        raise GateBlocked("HA_REGISTRY_UNAVAILABLE") from None
    active = [entry for entry in records
              if entry.get("domain") == "genvex_remote"
              and entry.get("disabled_by") is None]
    require(len(active) == 1, "HA_REMOTE_CONFIG_ENTRY")
    registered = [entity["entity_id"] for entity in entities
                  if entity.get("platform") == "genvex_remote"
                  and type(entity.get("entity_id")) is str]
    require(len(registered) == 6 and len(set(registered)) == 6,
            "HA_REMOTE_SIX_ENTITIES")
    print("HA_REMOTE_ENTITY_COUNT:", len(registered), flush=True)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args != ["--execute-readonly"]:
        return 2
    print("===== DEV5 POST-INSTALL GATE =====", flush=True)
    try:
        app = command_json(["ha", "apps", "info", APP, "--raw-json"])
        require(app.get("version") == "0.1.0-dev5", "INSTALLED_DEV5")
        require(app.get("state") == "stopped", "DEV5_STOPPED")
        require(app.get("boot") == "manual", "MANUAL_BOOT")
        opts = app.get("options")
        require(type(opts) is dict and opts.get("persistent_session") is True
                and opts.get("poll_seconds") == 60
                and type(opts.get("ipc_token")) is str
                and 40 <= len(opts["ipc_token"]) <= 128,
                "PERSISTENT_OPTIONS")
        try:
            docker = subprocess.run(
                ["docker", "inspect", CONTAINER, "--format", "{{json .}}"],
                capture_output=True, text=True, stdin=subprocess.DEVNULL,
                timeout=40,
            )
            running = docker.returncode == 0 and json.loads(
                docker.stdout
            )["State"]["Running"] is True
        except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
            raise GateBlocked("CONTAINER_STATE_UNKNOWN") from None
        require(not running, "CONTAINER_NOT_RUNNING")

        require(inspect_source(SOURCE, EXPECTED, True) == 20,
                "DEV5_SOURCE_20_BLOBS")
        require(inspect_source(BACKUP_SOURCE, UNCHANGED_DEV4, False) == 5
                and b'version: "0.1.0-dev4"' in (
                    BACKUP_SOURCE / "config.yaml"
                ).read_bytes().splitlines(), "DEV4_SOURCE_BACKUP")

        backups = command_json(["ha", "backups", "list", "--raw-json"], 90)
        inventory = backups.get("backups")
        require(type(inventory) is list and len(inventory) > BEFORE_BACKUP_COUNT,
                "BACKUP_COUNT_INCREASED")
        print("BACKUP_INVENTORY_COUNT:", len(inventory))
        found = find_new_backup(
            inventory, lambda slug: command_json(
                ["ha", "backups", "info", slug, "--raw-json"], 90
            ),
        )
        require(found is not None, "DEV4_SUPERVISOR_BACKUP")
        ident, date = found
        print("BACKUP_ID:", ident)
        print("BACKUP_DATE_UTC:", date)
        check_registry()
        print("DEV5_GATE_RESULT: PASS")
        return 0
    except GateBlocked as err:
        print("DEV5_GATE_RESULT: BLOCKED")
        print("ERROR_CATEGORY:", str(err))
        return 1
    except Exception as err:
        print("DEV5_GATE_RESULT: BLOCKED")
        print("ERROR_CATEGORY:", type(err).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
