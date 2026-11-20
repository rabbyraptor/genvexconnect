#!/usr/bin/env python3
"""Development HAOS App bootstrap: secrets never appear in argv or logs.

The profile is copied from the explicitly provisioned read-only /share path
into the App's private /data directory before the native polling service starts.
The Supervisor App option store is NOT a hardware-backed secret vault.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import stat
import tempfile

from ipc_auth import authorize_read
from polling_runtime import run
from sensor_model import remote_hostname

DATA = Path("/data")
SOURCE_PROFILE = Path("/share/genvex-remote-profile")
PROFILE = DATA / "profile"
TOKEN = DATA / "ipc-token"
OPTIONS = DATA / "options.json"
PROBE = Path("/opt/genvex-remote/runtime/probe_remote_snapshot.py")


def read_options(path: Path = OPTIONS) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 8192:
        raise ValueError("Invalid App options file")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Invalid App options")
    device = data.get("device_id")
    remote_hostname(device)
    for field in ("identity", "unlock_secret"):
        value = data.get(field)
        if not isinstance(value, str) or not value or len(value) > 1024 or any(
            char in value for char in "\r\n\x00"
        ):
            raise ValueError("Invalid App credential option")
    token = data.get("ipc_token")
    authorize_read(token, token)
    poll = data.get("poll_seconds", 60)
    if type(poll) is not int or not 60 <= poll <= 3600:
        raise ValueError("Invalid poll interval")
    return data


def private_copy(source: Path, destination: Path) -> None:
    info = source.lstat()
    if not stat.S_ISREG(info.st_mode) or not 1 <= info.st_size <= 131072:
        raise ValueError("Invalid profile file")
    # Do not follow symlinks; reject swapped file types and excessive data.
    fd = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        with os.fdopen(fd, "rb") as stream:
            content = stream.read(131073)
    except Exception:
        raise
    if not 1 <= len(content) <= 131072 or b"-----BEGIN " not in content:
        raise ValueError("Invalid PEM profile file")
    tmp_fd, tmp_name = tempfile.mkstemp(dir=destination.parent, prefix=".profile-")
    try:
        with os.fdopen(tmp_fd, "wb") as stream:
            stream.write(content)
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, destination)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def prepare_private_profile(source: Path = SOURCE_PROFILE,
                            target: Path = PROFILE) -> None:
    if source.is_symlink() or not source.is_dir():
        raise ValueError("Missing private profile source")
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    target.chmod(0o700)
    for name in ("client.crt", "client-encrypted.key"):
        private_copy(source / name, target / name)


def write_token(token: str, path: Path = TOKEN) -> None:
    authorize_read(token, token)
    fd, temp_path = tempfile.mkstemp(dir=path.parent, prefix=".ipc-token-")
    try:
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            stream.write(token + "\n")
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def main() -> None:
    try:
        options = read_options()
        prepare_private_profile()
        write_token(options["ipc_token"])
        config = {
            "device_id": options["device_id"],
            "identity": options["identity"],
            "unlock_secret": options["unlock_secret"],
            "profile_dir": str(PROFILE),
            "probe_file": str(PROBE),
            "token_file": str(TOKEN),
            "bind_host": "0.0.0.0",
            "poll_seconds": options.get("poll_seconds", 60),
        }
        print("Genvex Remote App: starting read-only polling on private App network", flush=True)
        asyncio.run(run(config))
    except Exception:
        # Do not leak credentials, paths, SDK errors or raw profile data.
        raise SystemExit(
            "Genvex Remote App: startup failed; check private profile and App options"
        ) from None


if __name__ == "__main__":
    main()
