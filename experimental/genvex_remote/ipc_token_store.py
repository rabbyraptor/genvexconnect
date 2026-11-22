"""Offline App-private IPC token lifecycle primitive for future onboarding.

Only generates/reuses a local 256-bit token; does not transfer it to Home
Assistant Core, expose any network API, modify Supervisor options or rotate an
already active token. A separately authenticated handoff is required.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat

from ipc_auth import authorize_read, new_ipc_token


class TokenStoreError(ValueError):
    """Sanitized token storage error (never contains token or path)."""


class PrivateIPCTokenStore:
    """Exclusive, persistent creation with strict private permissions."""

    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def _parent(self) -> None:
        try:
            info = self.directory.lstat()
            if (not stat.S_ISDIR(info.st_mode)
                    or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) != 0o700):
                raise TokenStoreError("Unsafe IPC token directory")
        except OSError:
            raise TokenStoreError("Unsafe IPC token directory") from None

    def read(self) -> str:
        """Read exactly one existing private token without symlink traversal."""
        self._parent()
        directory_fd = os.open(
            self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        )
        try:
            fd = os.open(
                "ipc-token", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd
            )
            try:
                info = os.fstat(fd)
                if (not stat.S_ISREG(info.st_mode)
                        or info.st_nlink != 1
                        or stat.S_IMODE(info.st_mode) != 0o600
                        or not 40 <= info.st_size <= 129):
                    raise TokenStoreError("Invalid private IPC token")
                with os.fdopen(fd, "rb", closefd=False) as stream:
                    payload = stream.read(130)
                token = payload.decode("ascii").strip()
                authorize_read(token, token)
                return token
            finally:
                os.close(fd)
        except (OSError, UnicodeError, ValueError):
            raise TokenStoreError("Invalid private IPC token") from None
        finally:
            os.close(directory_fd)

    def ensure(self) -> str:
        """Reuse existing token or create one with O_EXCL; never overwrite."""
        self._parent()
        try:
            return self.read()
        except TokenStoreError:
            # An existing but malformed token must never be overwritten.
            if os.path.lexists(self.directory / "ipc-token"):
                raise
        value = new_ipc_token()
        directory_fd = os.open(
            self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        )
        try:
            try:
                fd = os.open(
                    "ipc-token",
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=directory_fd,
                )
            except FileExistsError:
                return self.read()
            with os.fdopen(fd, "wb") as stream:
                stream.write((value + "\n").encode("ascii"))
                stream.flush()
                os.fsync(stream.fileno())
            os.fsync(directory_fd)
            return value
        except (OSError, ValueError):
            raise TokenStoreError("Unable to initialize private IPC token") from None
        finally:
            os.close(directory_fd)
