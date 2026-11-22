#!/usr/bin/env python3
"""DEV4 -> DEV5 source + Supervisor App update; no automatic App restart.

Prepared from a pinned source archive. Reads only App metadata/source and the
archive. Credentials are compared in-memory, never printed or copied.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys

APP = "local_genvex_nabto_remote"
CONTAINER = "app_local_genvex_nabto_remote"
BASE = Path("/mnt/data/supervisor/apps/local")
SOURCE = BASE / "genvex_nabto_remote"
STAGE = BASE / ".genvex-remote-dev5-source-stage"
BACKUP = BASE / ".genvex-remote-dev4-source-backup"
OLD_VERSION = "0.1.0-dev4"
NEW_VERSION = "0.1.0-dev5"
MAX_ARCHIVE_BYTES = 1_000_000
REQUIRED = frozenset({
    "Dockerfile", "config.yaml", "run.sh",
    "runtime/app_bootstrap.py", "runtime/profile_provision.py",
    "runtime/polling_runtime.py", "runtime/persistent_sdk_adapter.py",
    "runtime/persistent_rpc45_worker.py", "runtime/snapshot_state.py",
})


class UpgradeBlocked(Exception):
    """Safe operator-facing category only."""


def command(argv: list[str], timeout: int = 120) -> str:
    try:
        result = subprocess.run(argv, capture_output=True, text=True,
                                stdin=subprocess.DEVNULL, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        raise UpgradeBlocked("COMMAND_UNAVAILABLE") from None
    if result.returncode:
        raise UpgradeBlocked("COMMAND_FAILED")
    return result.stdout


def data_from_supervisor() -> dict:
    try:
        result = json.loads(command(["ha", "apps", "info", APP, "--raw-json"], 50))
        value = result["data"]
        if type(value) is not dict:
            raise ValueError
        return value
    except (KeyError, ValueError, TypeError):
        raise UpgradeBlocked("APP_INFO_INVALID") from None


def docker_running() -> bool:
    try:
        info = json.loads(command([
            "docker", "inspect", CONTAINER, "--format", "{{json .}}"
        ], 40))
        return info["State"]["Running"] is True
    except UpgradeBlocked:
        return False
    except (KeyError, ValueError, TypeError):
        raise UpgradeBlocked("CONTAINER_INFO_INVALID") from None


def options_of(data: dict) -> dict:
    options = data.get("options")
    if (type(options) is not dict
            or options.get("persistent_session") is not True
            or options.get("poll_seconds") != 60
            or type(options.get("ipc_token")) is not str
            or not 40 <= len(options["ipc_token"]) <= 128
            or type(options.get("unlock_secret")) is not str
            or not options["unlock_secret"]):
        raise UpgradeBlocked("PERSISTENT_OPTIONS_INVALID")
    return options


def require_installed(*, stopped: bool) -> dict:
    info = data_from_supervisor()
    allowed = {"stopped"} if stopped else {"started"}
    if (info.get("version") != OLD_VERSION
            or info.get("boot") != "manual"
            or info.get("state") not in allowed
            or docker_running() != (info["state"] == "started")):
        raise UpgradeBlocked("INSTALLED_DEV4_STATE_INVALID")
    options_of(info)
    return info


def verify_old_source() -> None:
    if not SOURCE.is_dir() or SOURCE.is_symlink():
        raise UpgradeBlocked("OLD_SOURCE_MISSING")
    for name in REQUIRED:
        item = SOURCE / name
        if not item.is_file() or item.is_symlink():
            raise UpgradeBlocked("OLD_SOURCE_INVALID")
    for item in SOURCE.rglob("*"):
        if item.is_symlink():
            raise UpgradeBlocked("OLD_SOURCE_SYMLINK")
        if item.is_file() and item.suffix in (".crt", ".key", ".pem", ".json"):
            raise UpgradeBlocked("OLD_SOURCE_PRIVATE_FILE")
    lines = (SOURCE / "config.yaml").read_bytes().splitlines()
    if not all(required in lines for required in (
        b'version: "0.1.0-dev4"',
        b"boot: manual_only", b"host_network: false",
        b"  persistent_session: bool",
    )):
        raise UpgradeBlocked("OLD_SOURCE_MANIFEST_INVALID")


def verify_archive(path: Path, digest: str) -> tuple[str, ...]:
    if (len(digest) != 64 or any(x not in "0123456789abcdef" for x in digest)
            or path.is_symlink() or not path.is_file()
            or not 100 <= path.stat().st_size <= MAX_ARCHIVE_BYTES):
        raise UpgradeBlocked("ARCHIVE_INPUT_INVALID")
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise UpgradeBlocked("ARCHIVE_HASH_MISMATCH")
    names = command(["tar", "-tzf", str(path)], 60).splitlines()
    details = command(["tar", "-tvzf", str(path)], 60).splitlines()
    if not 10 <= len(names) <= 100 or len(names) != len(details):
        raise UpgradeBlocked("ARCHIVE_LIST_INVALID")
    seen = set()
    for name, detail in zip(names, details):
        parts = PurePosixPath(name).parts
        if (name in seen or not detail.startswith("-") or len(name) > 160
                or ".." in parts or not (
                    len(parts) == 2 and parts[0] == "genvex_nabto_remote"
                    and parts[1] in ("Dockerfile", "config.yaml", "run.sh")
                    or len(parts) == 3
                    and parts[:2] == ("genvex_nabto_remote", "runtime")
                    and parts[2].endswith(".py")
                    and not parts[2].startswith(".")
                )):
            raise UpgradeBlocked("ARCHIVE_MEMBER_INVALID")
        seen.add(name)
    if not {"genvex_nabto_remote/" + name for name in REQUIRED} <= seen:
        raise UpgradeBlocked("ARCHIVE_FILES_MISSING")
    manifest = command(["tar", "-xOzf", str(path),
                        "genvex_nabto_remote/config.yaml"], 45)
    lines = manifest.encode().splitlines()
    if not all(expected in lines for expected in (
        b'version: "0.1.0-dev5"', b"boot: manual_only",
        b"host_network: false", b"  persistent_session: bool",
        b"  persistent_session: false",
    )):
        raise UpgradeBlocked("DEV5_MANIFEST_INVALID")
    return tuple(sorted(seen))


def preflight(path: Path, digest: str) -> tuple[dict, tuple[str, ...]]:
    names = verify_archive(path, digest)
    prior = require_installed(stopped=False)
    verify_old_source()
    if (STAGE.exists() or STAGE.is_symlink()
            or BACKUP.exists() or BACKUP.is_symlink()):
        raise UpgradeBlocked("TRANSACTION_PATH_OCCUPIED")
    if shutil.disk_usage(BASE).free < 512 * 1024 * 1024:
        raise UpgradeBlocked("INSUFFICIENT_SPACE")
    if "--backup" not in command(["ha", "apps", "update", "--help"], 40):
        raise UpgradeBlocked("BACKUP_FLAG_NOT_SUPPORTED")
    print("ARCHIVE_MEMBERS:", len(names), flush=True)
    print("FROM_VERSION:", OLD_VERSION, flush=True)
    print("TO_VERSION:", NEW_VERSION, flush=True)
    print("PERSISTENT_MODE: RETAIN", flush=True)
    print("DEV5_PREFLIGHT: PASS", flush=True)
    return prior, names


def apply(path: Path, digest: str) -> None:
    prior, names = preflight(path, digest)
    prior_options = options_of(prior)

    STAGE.mkdir(mode=0o700)
    try:
        command(["tar", "-xzf", str(path), "-C", str(STAGE)], 90)
        unpacked = STAGE / "genvex_nabto_remote"
        if not unpacked.is_dir() or unpacked.is_symlink():
            raise UpgradeBlocked("STAGED_SOURCE_INVALID")
        for name in names:
            relative = PurePosixPath(name).relative_to("genvex_nabto_remote")
            target = unpacked.joinpath(*relative.parts)
            if not target.is_file() or target.is_symlink():
                raise UpgradeBlocked("STAGED_FILE_INVALID")
        print("SOURCE_STAGED: PASS", flush=True)

        print("STOP_DEV4: REQUESTED", flush=True)
        command(["ha", "apps", "stop", APP], 180)
        require_installed(stopped=True)
        verify_old_source()
        print("DEV4_STOPPED_AND_RECHECKED: PASS", flush=True)

        SOURCE.rename(BACKUP)
        try:
            unpacked.rename(SOURCE)
        except BaseException:
            BACKUP.rename(SOURCE)
            raise
        print("SOURCE_SWAP_DEV5: PASS", flush=True)
    finally:
        if STAGE.exists():
            shutil.rmtree(STAGE)

    print("DEV4_SOURCE_BACKUP: RETAINED", flush=True)
    print("STORE_RELOAD: REQUESTED", flush=True)
    command(["ha", "store", "reload"], 120)
    offered = data_from_supervisor()
    if (offered.get("version") != OLD_VERSION
            or offered.get("version_latest") != NEW_VERSION
            or offered.get("update_available") is not True
            or offered.get("state") != "stopped"):
        raise UpgradeBlocked("DEV5_NOT_OFFERED")
    print("DEV5_OFFERED: PASS", flush=True)

    print("SUPERVISOR_UPDATE_WITH_BACKUP: REQUESTED", flush=True)
    command(["ha", "apps", "update", APP, "--backup"], 1800)
    installed = data_from_supervisor()
    if (installed.get("version") != NEW_VERSION
            or installed.get("state") != "stopped"
            or installed.get("boot") != "manual"
            or docker_running()):
        raise UpgradeBlocked("DEV5_POST_UPDATE_STATE_INVALID")
    if options_of(installed) != prior_options:
        raise UpgradeBlocked("APP_OPTIONS_CHANGED")
    print("INSTALLED_DEV5_STOPPED: PASS", flush=True)
    print("PERSISTENT_OPTIONS_UNCHANGED: PASS", flush=True)
    print("SUPERVISOR_BACKUP_REQUESTED: PASS", flush=True)
    print("DEV5_UPGRADE_RESULT: PASS", flush=True)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 3 or args[0] not in (
        "--validate-archive", "--preflight", "--apply"
    ):
        print("Usage: dev5_upgrade_transaction.py --validate-archive|--preflight|--apply ARCHIVE SHA256")
        return 2
    try:
        archive = Path(args[1])
        if args[0] == "--validate-archive":
            names = verify_archive(archive, args[2])
            print("ARCHIVE_MEMBERS:", len(names))
            print("DEV5_ARCHIVE_GATE: PASS")
        elif args[0] == "--preflight":
            preflight(archive, args[2])
        else:
            apply(archive, args[2])
        return 0
    except UpgradeBlocked as exc:
        print("DEV5_UPGRADE_RESULT: BLOCKED")
        print("ERROR_CATEGORY:", str(exc))
        return 1
    except Exception:
        print("DEV5_UPGRADE_RESULT: BLOCKED")
        print("ERROR_CATEGORY: UNEXPECTED_FAILURE")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
