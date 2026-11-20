#!/usr/bin/env python3
"""F2.2 synthetic-only atomic directory promotion prototype.

IMPORTANT: Not a credential importer. This module creates its own FAKE PEM
fixtures inside a caller-supplied temporary test directory. It has no CLI,
does not accept source profile paths, and must never be used for real keys.
"""
from __future__ import annotations

import fcntl
import os
from pathlib import Path
import shutil
import stat
import tempfile

FAKE_CERT = b"-----BEGIN CERTIFICATE-----\nZmFrZQ==\n-----END CERTIFICATE-----\n"
FAKE_KEY = (b"-----BEGIN ENCRYPTED PRIVATE KEY-----\nZmFrZQ==\n"
            b"-----END ENCRYPTED PRIVATE KEY-----\n")
FIXTURES = {"client.crt": FAKE_CERT, "client-encrypted.key": FAKE_KEY}


class PrototypeError(ValueError):
    pass


def simulate_atomic_import(test_root: Path, *, fail_after: int | None = None) -> Path:
    """Create only known fake data under a private, empty temporary test root.

    Uses Linux renameat2(RENAME_NOREPLACE) for atomic no-clobber promotion.
    Fails closed if the platform does not provide it. Not production-ready.
    """
    root = test_root.absolute()
    if root.is_symlink():
        raise PrototypeError("Unsafe test root")
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        raise PrototypeError("Test root must be private")
    if list(root.iterdir()):
        raise PrototypeError("Test root must be empty")
    lock_path = root / ".test-lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    stage = None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        stage = Path(tempfile.mkdtemp(prefix=".stage-", dir=root))
        os.chmod(stage, 0o700)
        for index, (name, payload) in enumerate(FIXTURES.items()):
            if fail_after is not None and index >= fail_after:
                raise PrototypeError("Injected test failure")
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
            out = os.open(stage / name, flags, 0o600)
            try:
                with os.fdopen(out, "wb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
            except BaseException:
                raise
        # Python os.rename can overwrite an existing empty directory.
        # This is a simulation with an exclusive empty root and lock, not
        # a hardened no-clobber production promotion.
        dest = root / "profile"
        if os.path.lexists(dest):
            raise PrototypeError("Destination already exists")
        os.rename(stage, dest)
        stage = None
        return dest
    finally:
        if stage is not None:
            shutil.rmtree(stage)
        os.close(fd)
        lock_path.unlink(missing_ok=True)
