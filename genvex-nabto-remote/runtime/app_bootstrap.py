#!/usr/bin/env python3
"""Development HAOS App bootstrap: secrets never appear in argv or logs.

The encrypted client profile must already exist in App-private /data/profile.
No shared /share mount or automatic credential import is permitted.
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
from sensor_model import remote_hostname

DATA = Path("/data")
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
    allowed = {
        "device_id", "identity", "unlock_secret", "ipc_token",
        "poll_seconds", "diagnostic_only", "persistent_session",
        "raw_registers_v3", "fan_level_v4",
    }
    if set(data) - allowed:
        raise ValueError("Unknown App option")
    diagnostic = data.get("diagnostic_only", False)
    if type(diagnostic) is not bool:
        raise ValueError("Diagnostic option must be a boolean")
    persistent_session = data.get("persistent_session", False)
    if type(persistent_session) is not bool:
        raise ValueError("Invalid persistent session option")
    raw_v3 = data.get("raw_registers_v3", False)
    if type(raw_v3) is not bool or (raw_v3 and not persistent_session):
        raise ValueError("Raw-register mode requires a persistent session")
    fan_v4 = data.get("fan_level_v4", False)
    if type(fan_v4) is not bool or (fan_v4 and not raw_v3):
        raise ValueError("Fan-level v4 requires raw v3")
    poll = data.get("poll_seconds", 60)
    if type(poll) is not int or not 60 <= poll <= 3600:
        raise ValueError("Invalid poll interval")

    if diagnostic is True:
        if persistent_session or raw_v3 or fan_v4:
            raise ValueError("Diagnostic mode cannot use persistent session")
        # Explicit opt-in only. Do not run a diagnostic process if the
        # configuration contains credentials that may belong to a live App.
        if any(data.get(key, "") != "" for key in (
            "device_id", "identity", "unlock_secret", "ipc_token"
        )):
            raise ValueError("Diagnostic mode requires empty credential fields")
        return data

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
    return data


def validate_private_profile(path: Path = PROFILE) -> None:
    """Fail closed unless both PEM credentials are already App-private.

    This is validation, NOT credential enrollment or migration. Provisioning
    credentials into /data/profile needs a separate, reviewed secure workflow.
    """
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        raise ValueError("App-private profile directory must have mode 0700")

    expected = {
        "client.crt": (
            b"-----BEGIN CERTIFICATE-----",
            b"-----END CERTIFICATE-----",
        ),
        "client-encrypted.key": (
            b"-----BEGIN ENCRYPTED PRIVATE KEY-----",
            b"-----END ENCRYPTED PRIVATE KEY-----",
        ),
    }
    for name, (header, footer) in expected.items():
        candidate = path / name
        fd = os.open(candidate, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode)
                    or info.st_mode & 0o077
                    or not 1 <= info.st_size <= 131072):
                raise ValueError("Unsafe App-private profile file")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                contents = stream.read(131073).strip()
            if (not contents.startswith(header)
                    or not contents.endswith(footer)
                    or b"\x00" in contents):
                raise ValueError("Invalid PEM profile file")
        finally:
            os.close(fd)


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


def run_diagnostic_only() -> None:
    """Never consult a profile or launch polling/SDK in diagnostic mode."""
    from diagnostic_http_server import DiagnosticHTTPServer

    server = DiagnosticHTTPServer(bind_host="0.0.0.0", port=18275)
    print("Genvex Remote App: DIAGNOSTIC ONLY; synthetic data, no Nabto", flush=True)
    server.serve_forever()


def main() -> None:
    try:
        options = read_options(OPTIONS)
        if options.get("diagnostic_only") is True:
            # Detect even dangling symlinks; fail closed if private material
            # from another mode is already present in this App's /data.
            if any(os.path.lexists(path) for path in (PROFILE, TOKEN)):
                raise ValueError("Diagnostic requires no private profile or token")
            run_diagnostic_only()
            return

        # Live-only imports and profile access happen strictly after the
        # diagnostic branch. No SDK code is imported by diagnostic startup.
        from polling_runtime import run
        validate_private_profile()
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
            "persistent_session": options.get("persistent_session", False),
            "raw_registers_v3": options.get("raw_registers_v3", False),
            "fan_level_v4": options.get("fan_level_v4", False),
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
