#!/usr/bin/env python3
"""Offline, read-only F2 profile preflight. NOT an importer.

Does not read or print PEM contents beyond bounded envelope validation.
Never opens a Nabto session, creates files, or accesses Supervisor.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import stat

FILES = {
    "client.crt": (b"-----BEGIN CERTIFICATE-----", b"-----END CERTIFICATE-----"),
    "client-encrypted.key": (
        b"-----BEGIN ENCRYPTED PRIVATE KEY-----",
        b"-----END ENCRYPTED PRIVATE KEY-----",
    ),
}
MAX_BYTES = 131072


class ProfilePreflightError(ValueError):
    pass


def _check_directory(path: Path) -> None:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        raise ProfilePreflightError("Unsafe source directory")


def _check_file(parent_fd: int, name: str, markers: tuple[bytes, bytes]) -> None:
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077
                or not 1 <= info.st_size <= MAX_BYTES):
            raise ProfilePreflightError("Unsafe source file")
        with os.fdopen(os.dup(fd), "rb") as handle:
            data = handle.read(MAX_BYTES + 1).strip()
        if (len(data) > MAX_BYTES or b"\x00" in data
                or not data.startswith(markers[0])
                or not data.endswith(markers[1])):
            raise ProfilePreflightError("Invalid source PEM envelope")
    finally:
        os.close(fd)


def check_source(source: Path) -> None:
    """Validate only; no destination or secret is ever written."""
    # Refuse symlinked source ancestors as well as final directory.
    absolute = source.absolute()
    for parent in (absolute, *absolute.parents):
        if parent.is_symlink():
            raise ProfilePreflightError("Symlinked source path")
    _check_directory(absolute)
    fd = os.open(absolute, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
            raise ProfilePreflightError("Unsafe source directory")
        for name, markers in FILES.items():
            _check_file(fd, name, markers)
    finally:
        os.close(fd)


def plan(source: Path, destination: Path) -> None:
    """Fail closed if target already exists; never create it."""
    check_source(source)
    if destination.is_symlink() or os.path.lexists(destination):
        raise ProfilePreflightError("Destination already exists")
    # The destination is deliberately not accepted as safe for importing:
    # its actual Supervisor mount mapping has not yet been verified.


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline read-only Nabto profile preflight")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    try:
        plan(args.source, args.destination)
    except (OSError, ProfilePreflightError):
        print("FAIL: profile preflight rejected (details suppressed)")
        return 1
    print("PASS: source PEM envelopes valid; destination absent; NO FILES WRITTEN")
    print("NOT APPROVED FOR IMPORT: Supervisor mount and atomic staging still unverified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
