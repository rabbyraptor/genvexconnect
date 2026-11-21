#!/usr/bin/env python3
"""DEV3 -> DEV4 local App source + Supervisor upgrade transaction.

Operator opt-in only. The source archive must be prepared from a pinned Git
revision. No private App data, credentials or Home Assistant Core files read.
This script does NOT start the upgraded App.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile

from dev4_source_baseline_preflight import (
    SOURCE, verify_source_tree, PreflightError,
)

SLUG = "local_genvex_nabto_remote"
CONTAINER = "app_local_genvex_nabto_remote"
BASE = SOURCE.parent
STAGE = BASE / ".genvex-remote-dev4-source-stage"
BACKUP = BASE / ".genvex-remote-dev3-source-backup"
NEEDED = {
    "Dockerfile", "config.yaml", "run.sh",
    "runtime/app_bootstrap.py", "runtime/profile_provision.py",
    "runtime/persistent_sdk_adapter.py", "runtime/persistent_rpc45_worker.py",
    "runtime/polling_runtime.py",
}
MAX_TOTAL_BYTES = 1_000_000
EXPECTED_VERSION = "0.1.0-dev4"


class UpgradeBlocked(Exception):
    pass


def run(command: list[str], *, timeout: int = 120, quiet: bool = True) -> str:
    p = subprocess.run(
        command, text=True, capture_output=True,
        stdin=subprocess.DEVNULL, timeout=timeout,
    )
    if p.returncode:
        raise UpgradeBlocked("EXTERNAL_COMMAND_FAILED")
    return p.stdout


def info() -> dict:
    try:
        payload = json.loads(run(["ha", "apps", "info", SLUG, "--raw-json"], timeout=45))
        result = payload["data"]
        if type(result) is not dict:
            raise ValueError()
        return result
    except (KeyError, TypeError, ValueError):
        raise UpgradeBlocked("APP_METADATA_INVALID") from None


def is_app_running() -> bool:
    result = subprocess.run(
        ["docker", "inspect", CONTAINER, "--format", "{{json .}}"],
        capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=40,
    )
    if result.returncode:
        return False
    payload = json.loads(result.stdout)
    return payload["State"]["Running"] is True


def require_old_state(*, stopped: bool) -> dict:
    metadata = info()
    if metadata.get("version") != "0.1.0-dev3" or metadata.get("boot") != "manual":
        raise UpgradeBlocked("NOT_INSTALLED_DEV3_MANUAL")
    allowed_states = {"stopped"} if stopped else {"started", "stopped"}
    if metadata.get("state") not in allowed_states:
        raise UpgradeBlocked("APP_STATE_UNEXPECTED")
    if is_app_running() != (metadata["state"] == "started"):
        raise UpgradeBlocked("APP_RUNNING_STATE_MISMATCH")
    return metadata


def _system_gzip_bytes(path: Path) -> bytes:
    """Decompress with system gzip when host Python lacks zlib.

    HAOS host can read .tar.gz using its system tar despite a minimal
    Python build missing zlib. Keep a strict expansion cap and do not
    print decompressed source or external tool diagnostics.
    """
    last_error = "GZIP_DECOMPRESS_UNAVAILABLE"
    for command in (["gzip", "-dc", str(path)],
                    ["busybox", "gzip", "-dc", str(path)]):
        try:
            proc = subprocess.Popen(
                command, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            continue
        try:
            assert proc.stdout is not None
            data = proc.stdout.read(4_194_305)
            if len(data) > 4_194_304:
                raise UpgradeBlocked("ARCHIVE_EXPANSION_LIMIT")
            proc.wait(timeout=30)
            if proc.returncode == 0:
                return data
            last_error = "GZIP_DECOMPRESS_FAILED"
        except subprocess.TimeoutExpired:
            last_error = "GZIP_DECOMPRESS_TIMEOUT"
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            if proc.stdout is not None:
                proc.stdout.close()
    raise UpgradeBlocked(last_error)


def open_source_archive(path: Path) -> tarfile.TarFile:
    """Use Python gzip if available, otherwise system gzip + raw tar."""
    try:
        return tarfile.open(path, "r:gz")
    except tarfile.CompressionError:
        uncompressed = _system_gzip_bytes(path)
        return tarfile.open(fileobj=io.BytesIO(uncompressed), mode="r:")


def verify_archive(archive_file: Path, expected_sha: str) -> tuple[str, ...]:
    if (len(expected_sha) != 64 or any(c not in "0123456789abcdef" for c in expected_sha)
            or archive_file.is_symlink() or not archive_file.is_file()
            or archive_file.stat().st_size > 1_000_000):
        raise UpgradeBlocked("ARCHIVE_INPUT_INVALID")
    if hashlib.sha256(archive_file.read_bytes()).hexdigest() != expected_sha:
        raise UpgradeBlocked("ARCHIVE_HASH_MISMATCH")
    try:
        with open_source_archive(archive_file) as archive:
            members = archive.getmembers()
            names = set()
            total = 0
            for item in members:
                parts = PurePosixPath(item.name).parts
                if not (
                    item.isfile()
                    and (len(parts) == 2 and parts[0] == "genvex_nabto_remote"
                         and parts[1] in {"Dockerfile", "config.yaml", "run.sh"}
                         or len(parts) == 3 and parts[:2] == (
                             "genvex_nabto_remote", "runtime"
                         ) and parts[2].endswith(".py") and not parts[2].startswith("."))
                    and ".." not in parts and item.name not in names
                    and 0 <= item.size <= 100_000
                ):
                    raise UpgradeBlocked("ARCHIVE_MEMBER_INVALID")
                names.add(item.name)
                total += item.size
                if total > MAX_TOTAL_BYTES:
                    raise UpgradeBlocked("ARCHIVE_TOO_LARGE")
            root = "genvex_nabto_remote/"
            if not {root + name for name in NEEDED} <= names:
                raise UpgradeBlocked("ARCHIVE_FILES_MISSING")
            manifest = archive.extractfile(root + "config.yaml").read()
            lines = manifest.splitlines()
            required = (
                b'version: "0.1.0-dev4"',
                b"boot: manual_only",
                b"host_network: false",
                b"  persistent_session: false",
                b"  persistent_session: bool",
            )
            if not all(line in lines for line in required):
                raise UpgradeBlocked("DEV4_MANIFEST_INVALID")
            return tuple(sorted(names))
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise UpgradeBlocked("ARCHIVE_READ_" + type(exc).__name__) from None


def diagnose_archive(archive_file: Path, expected_sha: str) -> None:
    """Only bounded environment/format diagnostics; never print archive data."""
    import importlib.util

    print("===== DEV4 ARCHIVE READ DIAGNOSTIC =====", flush=True)
    print("PYTHON_ZLIB:", "AVAILABLE" if importlib.util.find_spec("zlib") else "MISSING")
    try:
        blob = archive_file.read_bytes()
        print("ARCHIVE_BYTES:", len(blob))
        print("ARCHIVE_SHA256:", "MATCH" if hashlib.sha256(blob).hexdigest() == expected_sha else "MISMATCH")
    except Exception as exc:
        print("ARCHIVE_LOCAL_READ:", type(exc).__name__)
        print("ARCHIVE_DIAGNOSTIC_COMPLETE")
        return
    try:
        with tarfile.open(archive_file, "r:gz") as tf:
            print("PYTHON_TAR_GZIP:", "PASS")
            print("PYTHON_TAR_MEMBERS:", len(tf.getmembers()))
    except Exception as exc:
        print("PYTHON_TAR_GZIP:", "FAIL_" + type(exc).__name__)
    try:
        with open_source_archive(archive_file) as tf:
            members = tf.getmembers()
            print("ARCHIVE_READER_FALLBACK: PASS")
            print("FALLBACK_TAR_MEMBERS:", len(members))
            manifest = tf.extractfile("genvex_nabto_remote/config.yaml")
            print("FALLBACK_MANIFEST_ACCESS:", "PASS" if manifest and manifest.read() else "FAIL")
    except Exception as exc:
        print("ARCHIVE_READER_FALLBACK:", "FAIL_" + type(exc).__name__)
    try:
        check = subprocess.run(
            ["tar", "-tzf", str(archive_file)],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=30,
        )
        print("SYSTEM_TAR_GZIP:", "PASS" if check.returncode == 0 else "FAIL")
        if check.returncode == 0:
            print("SYSTEM_TAR_MEMBERS:", len(check.stdout.splitlines()))
    except Exception as exc:
        print("SYSTEM_TAR_GZIP:", "FAIL_" + type(exc).__name__)
    print("ARCHIVE_DIAGNOSTIC_COMPLETE", flush=True)


def unpack(archive_file: Path, names: tuple[str, ...], target: Path) -> Path:
    target.mkdir(mode=0o700)
    dest = target / "genvex_nabto_remote"
    dest.mkdir(mode=0o700)
    (dest / "runtime").mkdir(mode=0o700)
    with open_source_archive(archive_file) as archive:
        for name in names:
            rel = PurePosixPath(name).relative_to("genvex_nabto_remote")
            path = dest.joinpath(*rel.parts)
            with archive.extractfile(name) as source, path.open("xb") as output:
                shutil.copyfileobj(source, output)
            path.chmod(0o755 if rel.as_posix() == "run.sh" else 0o644)
    return dest


def confirm_options_disabled() -> None:
    data = info()
    options = data.get("options", {})
    if options is not None:
        if type(options) is not dict:
            raise UpgradeBlocked("APP_OPTIONS_INVALID")
        if options.get("persistent_session", False) is not False:
            raise UpgradeBlocked("PERSISTENT_MODE_NOT_DISABLED")


def apply(archive_file: Path, expected_sha: str) -> None:
    names = verify_archive(archive_file, expected_sha)
    print("SOURCE_ARCHIVE_VERIFIED:", len(names), flush=True)
    prior = require_old_state(stopped=False)
    verify_source_tree(SOURCE)
    if (STAGE.exists() or STAGE.is_symlink()
            or BACKUP.exists() or BACKUP.is_symlink()):
        raise UpgradeBlocked("TRANSACTION_PATH_OCCUPIED")
    if shutil.disk_usage(BASE).free < 512 * 1024 * 1024:
        raise UpgradeBlocked("INSUFFICIENT_DISK_SPACE")
    if "--backup" not in run(["ha", "apps", "update", "--help"]):
        raise UpgradeBlocked("SUPERVISOR_BACKUP_UNSUPPORTED")
    print("INSTALLED_DEV3_SOURCE_VERIFIED: PASS", flush=True)

    try:
        staging_source = unpack(archive_file, names, STAGE)
        if prior["state"] == "started":
            print("STOPPING_DEV3: REQUESTED", flush=True)
            run(["ha", "apps", "stop", SLUG], timeout=180)
        require_old_state(stopped=True)
        verify_source_tree(SOURCE)
        print("DEV3_STOPPED_AND_REVERIFIED: PASS", flush=True)

        # Source swap: restore the original immediately if the second rename
        # fails. A successful backup is preserved for explicit rollback.
        SOURCE.rename(BACKUP)
        try:
            staging_source.rename(SOURCE)
        except Exception:
            BACKUP.rename(SOURCE)
            raise
        print("SOURCE_SWAP_DEV4: PASS", flush=True)
    finally:
        if STAGE.exists() and STAGE.is_dir():
            shutil.rmtree(STAGE)

    if not (SOURCE / "config.yaml").is_file():
        raise UpgradeBlocked("STAGED_SOURCE_MISSING")
    print("SOURCE_BACKUP_DEV3: RETAINED", flush=True)

    print("SUPERVISOR_STORE_RELOAD: REQUESTED", flush=True)
    run(["ha", "store", "reload"], timeout=120)
    offered = info()
    if not (offered.get("version") == "0.1.0-dev3"
            and offered.get("version_latest") == EXPECTED_VERSION
            and offered.get("update_available") is True
            and offered.get("state") == "stopped"):
        raise UpgradeBlocked("SUPERVISOR_UPDATE_NOT_OFFERED")
    print("SUPERVISOR_UPDATE_AVAILABLE: PASS", flush=True)

    print("SUPERVISOR_BACKUP_AND_UPDATE: REQUESTED", flush=True)
    run(["ha", "apps", "update", SLUG, "--backup"], timeout=1800)
    installed = info()
    if not (installed.get("version") == EXPECTED_VERSION
            and installed.get("state") == "stopped"
            and installed.get("boot") == "manual"
            and not is_app_running()):
        raise UpgradeBlocked("POST_UPDATE_STATE_UNEXPECTED")
    confirm_options_disabled()
    print("INSTALLED_DEV4_STOPPED: PASS", flush=True)
    print("PERSISTENT_SESSION_DISABLED: PASS", flush=True)
    print("SUPERVISOR_BACKUP_REQUESTED: PASS", flush=True)
    print("DEV4_UPGRADE_RESULT: PASS", flush=True)


def main() -> int:
    if len(sys.argv) != 4 or sys.argv[1] not in ("--validate-archive", "--diagnose-archive", "--apply"):
        print("Usage: python3 dev4_upgrade_transaction.py --validate-archive|--apply ARCHIVE SHA256", file=sys.stderr)
        return 2
    archive, digest = Path(sys.argv[2]), sys.argv[3]
    try:
        if sys.argv[1] == "--diagnose-archive":
            diagnose_archive(archive, digest)
        elif sys.argv[1] == "--validate-archive":
            print("ARCHIVE_MEMBERS:", len(verify_archive(archive, digest)))
            print("DEV4_ARCHIVE_GATE: PASS")
        else:
            apply(archive, digest)
        return 0
    except UpgradeBlocked as e:
        print("DEV4_UPGRADE_RESULT: BLOCKED", flush=True)
        print("ERROR_CATEGORY:", e.args[0], flush=True)
        return 1
    except Exception as e:
        print("DEV4_UPGRADE_RESULT: BLOCKED", flush=True)
        print("ERROR_CATEGORY:", type(e).__name__, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
