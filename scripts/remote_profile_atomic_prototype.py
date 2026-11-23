#!/usr/bin/env python3
"""F2.3 synthetic-only atomic directory promotion prototype.

Creates only built-in FAKE PEM fixtures in a private empty disposable test
root. Not a credential importer; cannot accept source profiles or real keys.
Linux-only no-clobber promotion; no Supervisor/HAOS integration.
"""
from __future__ import annotations

import ctypes
import errno
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
_RENAME_NOREPLACE = 1


class PrototypeError(ValueError):
    pass


def _rename_noreplace(root_fd: int, staged: str, target: str) -> None:
    """Atomic no-clobber rename on Linux. Never fall back to os.rename."""
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        renameat2 = libc.renameat2
    except AttributeError as exc:
        raise PrototypeError("Atomic no-replace unavailable") from exc
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p,
                          ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    if renameat2(root_fd, os.fsencode(staged), root_fd,
                 os.fsencode(target), _RENAME_NOREPLACE) != 0:
        code = ctypes.get_errno()
        if code in (errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP):
            raise PrototypeError("Atomic no-replace unsupported")
        if code == errno.EEXIST:
            raise PrototypeError("Destination exists")
        raise OSError(code, "Atomic promotion failed")


def _check_test_root(root: Path) -> int:
    absolute = root.absolute()
    # Protect against symlink ancestors and ensure this is an empty disposable
    # test root, not a production HAOS data directory.
    for part in (absolute, *absolute.parents):
        if part.is_symlink():
            raise PrototypeError("Symlinked test root")
    fd = os.open(absolute, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
            raise PrototypeError("Test root must be private")
        if os.listdir(fd):
            raise PrototypeError("Test root must be empty")
        return fd
    except BaseException:
        os.close(fd)
        raise


def simulate_atomic_import(test_root: Path, *, fail_after: int | None = None,
                           before_promote=None) -> Path:
    """Stage artificial cert/key and atomically publish without overwriting.

    before_promote is a synthetic-only test hook. It receives root Path and
    runs after staging and before rename, to simulate a competing creator.
    """
    root = test_root.absolute()
    root_fd = _check_test_root(root)
    stage = None
    promoted = False
    try:
        # The lock is private and never removed while held, avoiding the
        # unlink/recreate lock inode race. The simulation requires empty root,
        # so subsequent calls reject the directory containing this lock.
        lock_fd = os.open(".test-lock", os.O_CREAT | os.O_EXCL | os.O_RDWR |
                          os.O_NOFOLLOW, 0o600, dir_fd=root_fd)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            stage = Path(tempfile.mkdtemp(prefix=".stage-", dir=root))
            os.chmod(stage, 0o700)
            for index, (name, payload) in enumerate(FIXTURES.items()):
                if fail_after is not None and index >= fail_after:
                    raise PrototypeError("Injected test failure")
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                out = os.open(stage / name, flags, 0o600)
                with os.fdopen(out, "wb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
            stage_fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(stage_fd)
            finally:
                os.close(stage_fd)
            if before_promote is not None:
                before_promote(root)
            _rename_noreplace(root_fd, stage.name, "profile")
            stage = None
            promoted = True
            os.fsync(root_fd)
            return root / "profile"
        finally:
            if stage is not None:
                shutil.rmtree(stage)
            os.close(lock_fd)
            # A private disposable test root is owned by the test. Leave
            # lock inode on success to reject repeated invocation. A failed
            # attempt removes it so the same test root can be retried.
            if not promoted:
                os.unlink(".test-lock", dir_fd=root_fd)
    finally:
        os.close(root_fd)
