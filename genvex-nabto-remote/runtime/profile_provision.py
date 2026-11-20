#!/usr/bin/env python3
"""Offline, one-time import into the App's private /data/profile directory.

Accept exactly two length-prefixed PEM payloads via stdin: certificate first,
then encrypted private key. No credentials in argv, environment or logs.
This command does NOT start Nabto, enroll identity or access the network.
It is not a user-facing deployment workflow; invoking it requires a separately
reviewed method to access the App-private /data volume.
"""
from __future__ import annotations

import ctypes
import errno
import os
from pathlib import Path
import stat
import struct
import sys
import tempfile

MAX_PEM = 131072
CERT_NAME = "client.crt"
KEY_NAME = "client-encrypted.key"


def _read_exact(stream, count: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < count:
        part = stream.read(count - len(chunks))
        if not part:
            raise ValueError("Truncated input")
        chunks.extend(part)
    return bytes(chunks)


def _payload(stream, *, header: bytes, footer: bytes) -> bytes:
    length = struct.unpack(">I", _read_exact(stream, 4))[0]
    if not 1 <= length <= MAX_PEM:
        raise ValueError("Invalid payload length")
    data = _read_exact(stream, length)
    normalized = data.strip()
    if not normalized.startswith(header) or not normalized.endswith(footer):
        raise ValueError("Invalid PEM envelope")
    if b"\x00" in normalized:
        raise ValueError("Invalid PEM payload")
    return data


def read_profile(stream) -> tuple[bytes, bytes]:
    certificate = _payload(
        stream, header=b"-----BEGIN CERTIFICATE-----",
        footer=b"-----END CERTIFICATE-----"
    )
    key = _payload(
        stream, header=b"-----BEGIN ENCRYPTED PRIVATE KEY-----",
        footer=b"-----END ENCRYPTED PRIVATE KEY-----"
    )
    if stream.read(1):
        raise ValueError("Unexpected input trailing bytes")
    return certificate, key


_RENAME_NOREPLACE = 1


def _rename_noreplace(parent_fd: int, staged: str, target: str) -> None:
    """Linux-only atomic promotion; never replace even an empty directory.

    Check-before-rename alone is vulnerable to a concurrent target creator.
    Fail closed if renameat2 is not available, rather than using os.rename.
    """
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        operation = libc.renameat2
    except AttributeError as exc:
        raise ValueError("Atomic no-replace unsupported") from exc
    operation.argtypes = [
        ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
        ctypes.c_char_p, ctypes.c_uint,
    ]
    operation.restype = ctypes.c_int
    if operation(
        parent_fd, os.fsencode(staged),
        parent_fd, os.fsencode(target), _RENAME_NOREPLACE,
    ) == 0:
        return
    code = ctypes.get_errno()
    if code == errno.EEXIST:
        raise FileExistsError("Private profile already provisioned")
    if code in (errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP):
        raise ValueError("Atomic no-replace unsupported")
    raise OSError(code, "Atomic private profile promotion failed")


def _write_private(path: Path, content: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        raise


def provision(stream, *, data_dir: Path = Path("/data")) -> None:
    """Create a new private profile, never overwrite existing credentials."""
    cert, key = read_profile(stream)
    info = data_dir.lstat()
    # Supervisor creates the App's /data as root-owned 0755 on the
    # verified HAOS host. This directory is NOT the private PEM boundary:
    # the newly published /data/profile must remain 0700 and files 0600.
    # Require the executing account to own /data and disallow writes by
    # group/others; a different owner could replace the staging directory
    # even when it cannot read the private PEMs.
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.geteuid()
        or info.st_mode & 0o022
    ):
        raise ValueError("Unsafe App data directory")
    target = data_dir / "profile"
    # An existing profile (including a symlink) is never replaced.
    if os.path.lexists(target):
        raise FileExistsError("Private profile already provisioned")
    stage = Path(tempfile.mkdtemp(prefix=".profile-stage-", dir=data_dir))
    try:
        stage.chmod(0o700)
        _write_private(stage / CERT_NAME, cert)
        _write_private(stage / KEY_NAME, key)
        # Sync both files and staging directory before atomic no-clobber
        # publication. A raced target can never be overwritten.
        stage_fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY |
                           getattr(os, "O_NOFOLLOW", 0))
        try:
            os.fsync(stage_fd)
        finally:
            os.close(stage_fd)
        parent_fd = os.open(data_dir, os.O_RDONLY | os.O_DIRECTORY |
                            getattr(os, "O_NOFOLLOW", 0))
        try:
            _rename_noreplace(parent_fd, stage.name, "profile")
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        if stage.exists():
            for name in (CERT_NAME, KEY_NAME):
                try:
                    (stage / name).unlink()
                except FileNotFoundError:
                    pass
            stage.rmdir()


def main() -> None:
    try:
        provision(sys.stdin.buffer)
    except Exception:
        # Do not leak credential material, file content, or source paths.
        raise SystemExit("Private Nabto profile provisioning failed") from None
    print("Private Nabto profile provisioned", flush=True)


if __name__ == "__main__":
    main()
