#!/usr/bin/env python3
"""Install the reviewed Genvex Remote HA component in one stopped/restart gate.

Runs on the HAOS host against a pinned archive sent by the operator runner.
The existing component is renamed to a retained local rollback directory.
Does not read, edit or print credentials or HA config-entry storage.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import time

HOME = Path("/mnt/data/supervisor/homeassistant")
COMPONENTS = HOME / "custom_components"
TARGET = COMPONENTS / "genvex_remote"
BACKUP = COMPONENTS / ".genvex_remote_pre_unified_backup"
STAGE = COMPONENTS / ".genvex_remote_unified_stage"
MAX_ARCHIVE_SIZE = 2_000_000
MAX_MEMBER_SIZE = 150_000
MIN_MEMBERS = 9
MAX_MEMBERS = 40


class InstallBlocked(Exception):
    """Operator-facing error category; never contains private HA data."""


def check_archive(path: Path, expected_sha256: str) -> list[tuple[str, bytes]]:
    if (type(expected_sha256) is not str
            or len(expected_sha256) != 64
            or any(c not in "0123456789abcdef" for c in expected_sha256)
            or path.is_symlink() or not path.is_file()
            or not 100 <= path.stat().st_size <= MAX_ARCHIVE_SIZE):
        raise InstallBlocked("ARCHIVE_INPUT_INVALID")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
        raise InstallBlocked("ARCHIVE_SHA256_MISMATCH")
    result: list[tuple[str, bytes]] = []
    names: set[str] = set()
    try:
        with tarfile.open(path, mode="r:gz") as tar:
            members = tar.getmembers()
            if not MIN_MEMBERS <= len(members) <= MAX_MEMBERS:
                raise InstallBlocked("ARCHIVE_MEMBER_COUNT_INVALID")
            for member in members:
                rel = PurePosixPath(member.name)
                parts = rel.parts
                # One top-level component folder; at most translations/xx.json.
                if (member.name in names or not member.isfile()
                        or len(parts) not in (2, 3)
                        or parts[0] != "genvex_remote"
                        or any(p.startswith(".") or p in ("..", "") for p in parts)
                        or (len(parts) == 3 and parts[1] != "translations")
                        or rel.suffix not in (".py", ".json")
                        or member.size < 1 or member.size > MAX_MEMBER_SIZE):
                    raise InstallBlocked("ARCHIVE_MEMBER_INVALID")
                names.add(member.name)
                fh = tar.extractfile(member)
                if fh is None:
                    raise InstallBlocked("ARCHIVE_MEMBER_INVALID")
                body = fh.read(MAX_MEMBER_SIZE + 1)
                if len(body) != member.size:
                    raise InstallBlocked("ARCHIVE_MEMBER_INVALID")
                if rel.suffix == ".py":
                    ast.parse(body.decode("utf-8", "strict"), filename=str(rel))
                else:
                    json.loads(body.decode("utf-8", "strict"))
                result.append((str(rel), body))
    except (tarfile.TarError, UnicodeError, SyntaxError, ValueError, OSError):
        raise InstallBlocked("ARCHIVE_CONTENT_INVALID") from None
    required = {
        "genvex_remote/__init__.py", "genvex_remote/manifest.json",
        "genvex_remote/config_flow.py", "genvex_remote/pairing_options.py",
        "genvex_remote/core_supervisor_loader.py",
        "genvex_remote/supervisor_pairing.py",
        "genvex_remote/runtime_client.py", "genvex_remote/coordinator.py",
        "genvex_remote/sensor.py", "genvex_remote/snapshot.py",
    }
    if not required <= names:
        raise InstallBlocked("ARCHIVE_REQUIRED_FILES_MISSING")
    manifest = json.loads(dict(result)["genvex_remote/manifest.json"])
    if (manifest.get("domain") != "genvex_remote"
            or manifest.get("config_flow") is not True):
        raise InstallBlocked("ARCHIVE_MANIFEST_INVALID")
    return result


def ha_cli(*args: str, timeout: int = 240) -> str:
    try:
        completed = subprocess.run(
            ["ha", *args], check=False, capture_output=True,
            text=True, stdin=subprocess.DEVNULL, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise InstallBlocked("HA_CLI_UNAVAILABLE") from None
    if completed.returncode != 0:
        raise InstallBlocked("HA_" + "_".join(args[:2]).upper() + "_FAILED")
    return completed.stdout


def check_core_started() -> None:
    for _ in range(20):
        try:
            data = json.loads(ha_cli("core", "info", "--raw-json", timeout=25))
            if data.get("data", {}).get("state") == "started":
                return
        except (ValueError, InstallBlocked):
            pass
        time.sleep(5)
    raise InstallBlocked("CORE_NOT_STARTED")


def apply(path: Path, sha256: str) -> None:
    files = check_archive(path, sha256)
    print("UNIFIED_ARCHIVE_SHA256: PASS", flush=True)
    print("UNIFIED_SOURCE_FILES:", len(files), flush=True)

    if (TARGET.is_symlink() or not TARGET.is_dir()
            or not (TARGET / "manifest.json").is_file()
            or BACKUP.exists() or BACKUP.is_symlink()
            or STAGE.exists() or STAGE.is_symlink()):
        raise InstallBlocked("INSTALLED_COMPONENT_STATE_INVALID")
    try:
        old_manifest = json.loads((TARGET / "manifest.json").read_text())
    except (OSError, ValueError):
        raise InstallBlocked("INSTALLED_COMPONENT_MANIFEST_INVALID") from None
    if old_manifest.get("domain") != "genvex_remote":
        raise InstallBlocked("INSTALLED_COMPONENT_DOMAIN_INVALID")

    STAGE.mkdir(mode=0o700)
    try:
        for rel, data in files:
            dest = STAGE / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("xb") as stream:
                stream.write(data)
            dest.chmod(0o644)
        prepared = STAGE / "genvex_remote"
        print("UNIFIED_COMPONENT_STAGED: PASS", flush=True)

        TARGET.rename(BACKUP)
        try:
            prepared.rename(TARGET)
        except BaseException:
            BACKUP.rename(TARGET)
            raise
        print("OLD_COMPONENT_BACKUP: RETAINED", flush=True)

        try:
            ha_cli("core", "check", timeout=240)
            print("HA_CORE_CHECK: PASS", flush=True)
            ha_cli("core", "restart", timeout=240)
            check_core_started()
            print("HA_CORE_RESTART: PASS", flush=True)
        except InstallBlocked:
            # Restore complete prior component, then ask HA Core to load it.
            shutil.rmtree(TARGET)
            BACKUP.rename(TARGET)
            print("UNIFIED_ROLLBACK: RESTORED", flush=True)
            try:
                ha_cli("core", "restart", timeout=240)
                check_core_started()
                print("PREVIOUS_COMPONENT_RESTART: PASS", flush=True)
            except InstallBlocked:
                print("PREVIOUS_COMPONENT_RESTART: FAILED", flush=True)
            raise
        print("UNIFIED_HA_INSTALL: PASS", flush=True)
    finally:
        if STAGE.exists():
            shutil.rmtree(STAGE)


def main() -> int:
    if len(sys.argv) != 4 or sys.argv[1] != "--apply":
        print("Usage: --apply SOURCE_ARCHIVE SHA256")
        return 2
    try:
        apply(Path(sys.argv[2]), sys.argv[3])
        return 0
    except InstallBlocked as exc:
        print("UNIFIED_HA_INSTALL: BLOCKED", flush=True)
        print("ERROR_CATEGORY:", str(exc), flush=True)
        return 1
    except Exception:
        print("UNIFIED_HA_INSTALL: BLOCKED", flush=True)
        print("ERROR_CATEGORY: UNEXPECTED_FAILURE", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
