"""Offline SDK 4.9.11 encrypted-key format candidate.

Produces OpenSSL PKCS8/PBES2 parameters matching the previously confirmed
working legacy Nabto profile. New key has NOT been tested with SDK 4.9.11.
RSA-1024 and PBES2/3DES are obsolete; compatibility-only.
"""
from __future__ import annotations
import os
import subprocess
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey


class KeyFormatError(Exception):
    """Sanitized error; never expose a key or raw OpenSSL diagnostics."""


def encrypt_legacy_pkcs8(key: RSAPrivateKey, passphrase: bytes) -> bytes:
    """PBES2 / PBKDF2-HMAC-SHA256 / 2048 iterations / 3DES-CBC.

    Passphrase travels via inherited FD pipe, not argv, environment or disk.
    Plaintext PEM private key is passed through stdin, not placed on disk.
    """
    if key.key_size != 1024:
        raise KeyFormatError("Legacy SDK candidate requires RSA-1024")
    if (not isinstance(passphrase, bytes) or len(passphrase) < 16
            or b"\n" in passphrase or b"\x00" in passphrase):
        raise KeyFormatError("Invalid unlock passphrase")

    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    read_fd, write_fd = os.pipe()
    try:
        try:
            os.write(write_fd, passphrase + b"\n")
        finally:
            os.close(write_fd)
        try:
            result = subprocess.run(
                ["openssl", "pkcs8", "-topk8", "-v2", "des3",
                 "-v2prf", "hmacWithSHA256", "-iter", "2048",
                 "-passout", f"fd:{read_fd}"],
                input=pem, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                check=False, timeout=20, pass_fds=(read_fd,),
            )
        except (OSError, subprocess.TimeoutExpired):
            raise KeyFormatError("Legacy key conversion unavailable") from None
    finally:
        os.close(read_fd)
    if (result.returncode != 0
            or not result.stdout.startswith(b"-----BEGIN ENCRYPTED PRIVATE KEY-----")):
        raise KeyFormatError("Legacy key conversion failed")
    return result.stdout
