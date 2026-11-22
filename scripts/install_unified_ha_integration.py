#!/usr/bin/env python3
"""Install the reviewed Genvex Remote HA component in one stopped/restart gate.

Runs on the HAOS host against a pinned archive sent by the operator runner.
The existing component is renamed to a retained local rollback directory.
Does not read, edit or print credentials or HA config-entry storage.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
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
    # The HAOS host's Python tarfile/gzip reader rejected the pinned archive.
    # Use the host's proven tar CLI instead (also used by the DEV6 gate).
    # Validate all names and regular-file types *before* reading any member;
    # never pass unvalidated paths to tar.
    def tar_command(*args: str) -> bytes:
        try:
            done = subprocess.run(
                ["tar", *args], capture_output=True,
                stdin=subprocess.DEVNULL, timeout=45, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise InstallBlocked("ARCHIVE_TAR_UNAVAILABLE") from None
        if done.returncode != 0:
            raise InstallBlocked("ARCHIVE_TAR_FAILED")
        return done.stdout

    try:
        names = tar_command("-tzf", str(path)).decode("utf-8", "strict").splitlines()
        details = tar_command("-tvzf", str(path)).decode("utf-8", "strict").splitlines()
    except UnicodeError:
        raise InstallBlocked("ARCHIVE_LIST_UTF8_INVALID") from None

    if (not MIN_MEMBERS <= len(names) <= MAX_MEMBERS
            or len(names) != len(details)):
        raise InstallBlocked("ARCHIVE_MEMBER_COUNT_INVALID")

    seen: set[str] = set()
    for name, detail in zip(names, details):
        rel = PurePosixPath(name)
        parts = rel.parts
        if (name in seen or not detail.startswith("-")
                or name != str(rel)
                or len(parts) not in (2, 3)
                or parts[0] != "genvex_remote"
                or any(p.startswith(".") or p in ("..", "") for p in parts)
                or (len(parts) == 3 and parts[1] != "translations")
                or rel.suffix not in (".py", ".json")
                or len(name) > 160):
            raise InstallBlocked("ARCHIVE_MEMBER_INVALID")
        seen.add(name)

    result: list[tuple[str, bytes]] = []
    for name in names:
        body = tar_command("-xOzf", str(path), name)
        if not 1 <= len(body) <= MAX_MEMBER_SIZE:
            raise InstallBlocked("ARCHIVE_MEMBER_INVALID")
        try:
            decoded = body.decode("utf-8", "strict")
        except UnicodeError:
            raise InstallBlocked("ARCHIVE_UTF8_INVALID") from None
        if name.endswith(".json"):
            try:
                json.loads(decoded)
            except ValueError:
                raise InstallBlocked("ARCHIVE_JSON_INVALID") from None
        result.append((name, body))
    required = {
        "genvex_remote/__init__.py", "genvex_remote/manifest.json",
        "genvex_remote/config_flow.py", "genvex_remote/pairing_options.py",
        "genvex_remote/core_supervisor_loader.py",
        "genvex_remote/supervisor_pairing.py",
        "genvex_remote/runtime_client.py", "genvex_remote/coordinator.py",
        "genvex_remote/sensor.py", "genvex_remote/snapshot.py",
    }
    if not required <= seen:
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
