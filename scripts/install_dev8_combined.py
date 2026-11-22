#!/usr/bin/env python3
"""Single versioned DEV8 App + HA source deployment on the HAOS host.

Receives one pinned, SHA-256 checked combined archive. CLI preflight reads
only host/source state; apply stops/updates the App once, then reloads Core
with retained source backups. No credentials or full options are printed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import socket
import subprocess
import sys
import time

BASE = Path("/mnt/data/supervisor/apps/local")
HA_HOME = Path("/mnt/data/supervisor/homeassistant")
APP_SOURCE = BASE / "genvex_nabto_remote"
HA_SOURCE = HA_HOME / "custom_components/genvex_remote"
APP_BACKUP = BASE / ".genvex-dev8-previous-app-source"
HA_BACKUP = HA_HOME / ".genvex-remote-pre-dev8"
APP_STAGE = BASE / ".genvex-dev8-source-stage"
HA_STAGE = HA_HOME / ".genvex-remote-dev8-stage"
APP_SLUG = "local_genvex_nabto_remote"
OLD_VERSION = "0.1.0-dev6"
NEW_VERSION = "0.1.0-dev8"
HA_VERSION = "0.2.0"
MAX_ARCHIVE = 2_000_000
MAX_MEMBER = 150_000


class ReleaseBlocked(Exception):
    """Explicit non-secret deployment gate failure category."""


def command(args: list[str], timeout: int = 120) -> str:
    try:
        completed = subprocess.run(
            args, capture_output=True, text=True,
            stdin=subprocess.DEVNULL, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ReleaseBlocked("HOST_COMMAND_UNAVAILABLE") from None
    if completed.returncode:
        raise ReleaseBlocked("HOST_COMMAND_FAILED") from None
    return completed.stdout


def ha_info(*args: str) -> dict:
    try:
        data = json.loads(command(["ha", *args, "--raw-json"], 60))
        result = data.get("data")
        if type(result) is not dict:
            raise ValueError
        return result
    except (ValueError, TypeError):
        raise ReleaseBlocked("SUPERVISOR_INFO_INVALID") from None


def allowed_member(name: str) -> bool:
    path = PurePosixPath(name)
    parts = path.parts
    if (
        path.as_posix() != name or len(name) > 200
        or any(part in ("", ".", "..") or part.startswith(".") for part in parts)
    ):
        return False
    if name == "DEV8_RELEASE_MANIFEST.json":
        return True
    if parts[0] == "genvex_nabto_remote":
        return (
            len(parts) == 2 and parts[1] in ("Dockerfile", "config.yaml", "run.sh")
            or len(parts) == 3 and parts[1] == "runtime"
            and parts[2].endswith(".py")
        )
    return (
        parts[:2] == ("custom_components", "genvex_remote")
        and (
            len(parts) == 3 and parts[2].endswith((".py", ".json"))
            or len(parts) == 4 and parts[2] == "translations"
            and parts[3].endswith(".json")
        )
    )


def verify_bundle(archive: Path, sha: str) -> dict[str, bytes]:
    """Read exact regular-file members through host-proven tar CLI."""
    if (
        re.fullmatch(r"[0-9a-f]{64}", sha) is None
        or archive.is_symlink() or not archive.is_file()
        or not 100 <= archive.stat().st_size <= MAX_ARCHIVE
        or hashlib.sha256(archive.read_bytes()).hexdigest() != sha
    ):
        raise ReleaseBlocked("BUNDLE_DIGEST_INVALID")
    names = command(["tar", "-tzf", str(archive)], 60).splitlines()
    details = command(["tar", "-tvzf", str(archive)], 60).splitlines()
    if not 30 <= len(names) <= 90 or len(names) != len(details):
        raise ReleaseBlocked("BUNDLE_LAYOUT_INVALID")
    if len(set(names)) != len(names):
        raise ReleaseBlocked("BUNDLE_DUPLICATE_MEMBER")
    files: dict[str, bytes] = {}
    for name, detail in zip(names, details):
        if not allowed_member(name) or not detail.startswith("-"):
            raise ReleaseBlocked("BUNDLE_UNEXPECTED_MEMBER")
        body = command(["tar", "-xOzf", str(archive), name], 50).encode(
            "latin1", "surrogateescape",
        )
        # The tar subprocess returns *text* in command(), which cannot safely
        # round-trip arbitrary byte sequences. All source members are UTF-8,
        # so require byte-preserving ASCII/UTF-8 re-encoding below.
        if not 1 <= len(body) <= MAX_MEMBER:
            raise ReleaseBlocked("BUNDLE_MEMBER_SIZE_INVALID")
        files[name] = body
    try:
        index = json.loads(files.pop("DEV8_RELEASE_MANIFEST.json").decode("utf-8"))
        app = files["genvex_nabto_remote/config.yaml"].decode("utf-8")
        ha = json.loads(files["custom_components/genvex_remote/manifest.json"])
    except (KeyError, ValueError, UnicodeError):
        raise ReleaseBlocked("BUNDLE_METADATA_INVALID") from None
    if (
        index.get("release") != "GENVEX_REMOTE_DEV8"
        or index.get("app_version") != NEW_VERSION
        or index.get("home_assistant_version") != HA_VERSION
        or index.get("snapshot_schema") != 3
        or index.get("rpc45_addresses") != [
            20, 21, 22, 23, 26, 24, 18, 19, 35, 36, 41, 42, 53, 40,
            114, 115, 50,
        ]
        or index.get("files") != {
            key: hashlib.sha256(value).hexdigest()
            for key, value in sorted(files.items())
        }
        or f'version: "{NEW_VERSION}"' not in app
        or ha.get("domain") != "genvex_remote"
        or ha.get("version") != HA_VERSION
        or "genvex_nabto_remote/runtime/raw_registers_v3.py" not in files
        or "custom_components/genvex_remote/raw_snapshot_v3.py" not in files
    ):
        raise ReleaseBlocked("BUNDLE_INTEGRITY_INVALID")
    return files


def core_api_ready(port: int, ssl: bool) -> bool:
    if type(port) is not int or not 1 <= port <= 65535 or type(ssl) is not bool:
        return False
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=4) as conn:
            conn.settimeout(4)
            if ssl:
                return True
            conn.sendall(
                b"GET /api/ HTTP/1.0\r\nHost: 127.0.0.1\r\n"
                b"Connection: close\r\n\r\n"
            )
            line = conn.recv(128).split(b"\r\n", 1)[0]
            return any(line.startswith(b"HTTP/1." + value) for value in (
                b"0 200", b"1 200", b"0 401", b"1 401", b"0 403", b"1 403",
            ))
    except (OSError, TimeoutError):
        return False


def check_core_ready() -> None:
    for _ in range(24):
        try:
            info = ha_info("core", "info")
            if (
                isinstance(info.get("version"), str)
                and core_api_ready(info.get("port", 8123), info.get("ssl", False))
            ):
                return
        except ReleaseBlocked:
            pass
        time.sleep(5)
    raise ReleaseBlocked("CORE_NOT_READY")


def app_options(options: object) -> dict:
    if (
        type(options) is not dict
        or options.get("persistent_session") is not True
        or options.get("poll_seconds") != 60
        or type(options.get("ipc_token")) is not str
        or not 40 <= len(options["ipc_token"]) <= 128
        or type(options.get("unlock_secret")) is not str
        or not options["unlock_secret"]
    ):
        raise ReleaseBlocked("APP_OPTIONS_INVALID")
    return dict(options)


def installed_preflight(files: dict[str, bytes]) -> dict:
    info = ha_info("apps", "info", APP_SLUG)
    if (
        info.get("version") != OLD_VERSION
        or info.get("boot") != "manual"
        or info.get("state") != "started"
    ):
        raise ReleaseBlocked("INSTALLED_APP_VERSION_OR_STATE_INVALID")
    options = app_options(info.get("options"))
    if (
        not APP_SOURCE.is_dir() or APP_SOURCE.is_symlink()
        or not HA_SOURCE.is_dir() or HA_SOURCE.is_symlink()
        or any(path.exists() or path.is_symlink() for path in (
            APP_BACKUP, HA_BACKUP, APP_STAGE, HA_STAGE,
        ))
        or not (APP_SOURCE / "config.yaml").is_file()
        or f'version: "{OLD_VERSION}"' not in (APP_SOURCE / "config.yaml").read_text()
        or not (HA_SOURCE / "manifest.json").is_file()
    ):
        raise ReleaseBlocked("INSTALLED_SOURCE_STATE_INVALID")
    try:
        ha_manifest = json.loads((HA_SOURCE / "manifest.json").read_text())
    except (OSError, ValueError):
        raise ReleaseBlocked("INSTALLED_HA_MANIFEST_INVALID") from None
    if ha_manifest.get("domain") != "genvex_remote":
        raise ReleaseBlocked("INSTALLED_HA_DOMAIN_INVALID")
    if shutil.disk_usage(BASE).free < 512 * 1024 * 1024:
        raise ReleaseBlocked("INSUFFICIENT_DISK")
    if "--backup" not in command(["ha", "apps", "update", "--help"], 30):
        raise ReleaseBlocked("APP_BACKUP_FLAG_UNAVAILABLE")
    check_core_ready()
    print("DEV8_BUNDLE_MEMBERS:", len(files) + 1, flush=True)
    print("DEV8_FROM_VERSION:", OLD_VERSION, flush=True)
    print("DEV8_TO_APP_VERSION:", NEW_VERSION, flush=True)
    print("DEV8_TO_HA_VERSION:", HA_VERSION, flush=True)
    print("DEV8_PREFLIGHT: PASS", flush=True)
    return options


def _materialize_stage(files: dict[str, bytes]) -> None:
    APP_STAGE.mkdir(mode=0o700)
    HA_STAGE.mkdir(mode=0o700)
    for name, body in files.items():
        path = PurePosixPath(name)
        if path.parts[0] == "genvex_nabto_remote":
            target = APP_STAGE.joinpath(*path.parts[1:])
        else:
            target = HA_STAGE.joinpath(*path.parts[2:])
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            output.write(body)
        target.chmod(0o755 if name.endswith("/run.sh") else 0o644)


def apply(archive: Path, sha: str) -> None:
    files = verify_bundle(archive, sha)
    previous_options = installed_preflight(files)
    app_installed = False
    app_swapped = False
    ha_swapped = False
    app_was_stopped = False
    try:
        _materialize_stage(files)
        print("DEV8_STAGING: PASS", flush=True)
        command(["ha", "apps", "stop", APP_SLUG], 180)
        app_was_stopped = True
        APP_SOURCE.rename(APP_BACKUP)
        try:
            APP_STAGE.rename(APP_SOURCE)
        except BaseException:
            APP_BACKUP.rename(APP_SOURCE)
            raise
        app_swapped = True
        print("DEV8_APP_SOURCE_SWAP: PASS", flush=True)
        command(["ha", "store", "reload"], 120)
        offered = ha_info("apps", "info", APP_SLUG)
        if (
            offered.get("version_latest") != NEW_VERSION
            or offered.get("update_available") is not True
        ):
            raise ReleaseBlocked("DEV8_APP_UPDATE_NOT_OFFERED")
        command(["ha", "apps", "update", APP_SLUG, "--backup"], 1800)
        installed = ha_info("apps", "info", APP_SLUG)
        if installed.get("version") != NEW_VERSION:
            raise ReleaseBlocked("DEV8_APP_NOT_INSTALLED")
        app_installed = True
        after_options = app_options(installed.get("options"))
        after_options.pop("raw_registers_v3", None) if (
            after_options.get("raw_registers_v3") is False
        ) else None
        original = dict(previous_options)
        original.pop("raw_registers_v3", None) if (
            original.get("raw_registers_v3") is False
        ) else None
        if after_options != original:
            raise ReleaseBlocked("APP_OPTIONS_NOT_PRESERVED")
        command(["ha", "apps", "start", APP_SLUG], 240)
        started = ha_info("apps", "info", APP_SLUG)
        if started.get("state") != "started":
            raise ReleaseBlocked("DEV8_APP_START_FAILED")
        print("DEV8_APP_INSTALLED_AND_STARTED: PASS", flush=True)

        HA_SOURCE.rename(HA_BACKUP)
        try:
            HA_STAGE.rename(HA_SOURCE)
        except BaseException:
            HA_BACKUP.rename(HA_SOURCE)
            raise
        ha_swapped = True
        command(["ha", "core", "check"], 240)
        command(["ha", "core", "restart"], 240)
        check_core_ready()
        print("DEV8_HA_COMPONENT_INSTALLED: PASS", flush=True)
        print("DEV8_COMBINED_INSTALL: PASS", flush=True)
    except BaseException:
        if ha_swapped and HA_BACKUP.is_dir():
            shutil.rmtree(HA_SOURCE)
            HA_BACKUP.rename(HA_SOURCE)
            print("DEV8_HA_ROLLBACK: RESTORED", flush=True)
            try:
                command(["ha", "core", "restart"], 240)
                check_core_ready()
            except ReleaseBlocked:
                print("DEV8_HA_ROLLBACK_RESTART: BLOCKED", flush=True)
        if not app_installed and app_swapped and APP_BACKUP.is_dir():
            shutil.rmtree(APP_SOURCE)
            APP_BACKUP.rename(APP_SOURCE)
            print("DEV8_APP_SOURCE_ROLLBACK: RESTORED", flush=True)
            try:
                command(["ha", "store", "reload"], 120)
            except ReleaseBlocked:
                pass
        if app_was_stopped and not app_installed:
            try:
                command(["ha", "apps", "start", APP_SLUG], 240)
            except ReleaseBlocked:
                print("DEV8_PREVIOUS_APP_START: BLOCKED", flush=True)
        raise
    finally:
        for path in (APP_STAGE, HA_STAGE):
            if path.is_dir():
                shutil.rmtree(path)


def main() -> int:
    if (
        len(sys.argv) != 4
        or sys.argv[1] not in ("--preflight", "--apply")
    ):
        print("Usage: --preflight|--apply BUNDLE SHA256")
        return 2
    try:
        archive, sha = Path(sys.argv[2]), sys.argv[3]
        if sys.argv[1] == "--preflight":
            installed_preflight(verify_bundle(archive, sha))
        else:
            apply(archive, sha)
        return 0
    except ReleaseBlocked as exc:
        print("DEV8_COMBINED_INSTALL: BLOCKED", flush=True)
        print("ERROR_CATEGORY:", str(exc), flush=True)
        return 1
    except Exception:
        print("DEV8_COMBINED_INSTALL: BLOCKED", flush=True)
        print("ERROR_CATEGORY: UNEXPECTED_FAILURE", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
