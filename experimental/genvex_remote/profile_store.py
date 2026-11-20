"""Crash-resilient private local credential generations for an HAOS runtime App.

Offline filesystem primitive. Input credentials MUST already be verified by
the enrollment layer. Caller should choose /data/identity as a private volume.

The active.json pointer is replaced atomically after all generation files
are durable. No automatic deletion of old generations: old identity can be
retained for rollback until the calling lifecycle manager rotates it safely.

No network, SDK, logging or environment-variable secrets.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import stat


class StoreError(Exception):
    """Sanitized storage error; do not expose private paths/secret data."""


_GEN_RE = re.compile(r"[0-9a-f]{32}\Z")


def _regular_file(path: Path) -> bool:
    info = path.lstat()  # rejects symlinks rather than following them
    return stat.S_ISREG(info.st_mode) and info.st_nlink == 1


def _secure_dir(path: Path) -> None:
    st = path.lstat()
    if not stat.S_ISDIR(st.st_mode) or stat.S_IMODE(st.st_mode) != 0o700:
        raise StoreError("Identity directory is not private")


def _persist_file(path: Path, data: bytes) -> None:
    if not isinstance(data, bytes) or not data or len(data) > 65536:
        raise StoreError("Invalid credential file")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=True) as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
    except BaseException:
        # fdopen closes fd as part of its context manager when successful
        raise


def _sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class PrivateProfileStore:
    """Private directory, versioned credential sets and atomic active pointer."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def _prepare_root(self) -> None:
        if self.root.exists() or self.root.is_symlink():
            _secure_dir(self.root)
        else:
            self.root.mkdir(parents=True, mode=0o700)
            _secure_dir(self.root)
        versions = self.root / "versions"
        if versions.exists() or versions.is_symlink():
            _secure_dir(versions)
        else:
            versions.mkdir(mode=0o700)
            _secure_dir(versions)

    def commit(self, *, certificate_pem: bytes, encrypted_key_pem: bytes,
               unlock_secret: bytes, identity: str) -> str:
        """Commit complete identity atomically; return opaque generation ID.

        Identity must already be validated by the enrollment layer. Unlock
        secret remains on the same disk as encrypted private key: file-system
        access control, not cryptographic protection from host compromise.
        """
        if (not isinstance(identity, str) or not identity.isascii()
                or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+", identity)
                or ".." in identity or "/" in identity or len(identity) > 254):
            raise StoreError("Invalid identity")
        self._prepare_root()
        versions = self.root / "versions"
        gen = secrets.token_hex(16)
        stage = versions / ("." + gen + ".staging")
        final = versions / gen
        stage.mkdir(mode=0o700)
        try:
            _persist_file(stage / "client.crt", certificate_pem)
            _persist_file(stage / "client-encrypted.key", encrypted_key_pem)
            _persist_file(stage / "unlock.secret", unlock_secret)
            _persist_file(stage / "identity.txt", identity.encode())
            _sync_directory(stage)
            os.replace(stage, final)
            _sync_directory(versions)
            pointer = self.root / (".active." + gen)
            _persist_file(pointer, json.dumps({"generation": gen}, separators=(",", ":")).encode())
            os.replace(pointer, self.root / "active.json")
            _sync_directory(self.root)
            return gen
        except BaseException:
            # Do not remove a committed generation: it may become active
            # even if an error is raised by a later fsync.
            if stage.exists():
                for child in stage.iterdir():
                    if child.is_file() and not child.is_symlink():
                        child.unlink()
                stage.rmdir()
            raise

    def load(self) -> dict[str, bytes]:
        """Load active credential set with no symlink traversal."""
        _secure_dir(self.root)
        active = self.root / "active.json"
        if not _regular_file(active) or stat.S_IMODE(active.stat().st_mode) != 0o600:
            raise StoreError("Invalid active identity metadata")
        try:
            raw = active.read_bytes()
            if len(raw) > 1024:
                raise StoreError("Invalid active identity metadata")
            metadata = json.loads(raw)
            generation = metadata["generation"]
            if not isinstance(generation, str) or not _GEN_RE.fullmatch(generation):
                raise StoreError("Invalid active identity metadata")
            folder = self.root / "versions" / generation
            _secure_dir(self.root / "versions")
            _secure_dir(folder)
            result = {}
            for name in ("client.crt", "client-encrypted.key", "unlock.secret", "identity.txt"):
                path = folder / name
                if not _regular_file(path):
                    raise StoreError("Invalid stored credential")
                if stat.S_IMODE(path.stat().st_mode) != 0o600:
                    raise StoreError("Invalid stored credential permissions")
                value = path.read_bytes()
                if not value or len(value) > 65536:
                    raise StoreError("Invalid stored credential")
                result[name] = value
            return result
        except (OSError, ValueError, TypeError, KeyError, UnicodeError):
            raise StoreError("Invalid active identity store") from None
