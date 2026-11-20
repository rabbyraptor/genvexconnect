"""Offline orchestration of CA enrollment with an injected transport.

The caller must supply a reviewed, TLS-verified, bounded registration
transport and independently pinned legacy CA. This module does no network
I/O and cannot silently register with the vendor.

After CA + key verification, commit to an atomic private /data profile store.
No keys or passwords are returned in EnrollmentResult.
"""
from __future__ import annotations

from dataclasses import dataclass
import secrets
from typing import Callable

from cryptography.hazmat.primitives import serialization

from certificate_trust import TrustError
from enrollment_core import (
    EnrollmentError, generate_candidate, normalize_email,
    verify_trusted_registration_reply,
)
from profile_store import PrivateProfileStore, StoreError
from sensor_model import remote_hostname


@dataclass(frozen=True)
class EnrollmentResult:
    generation: str
    device_hostname: str
    expires_at: str


def enroll_with_transport(
    *,
    device_id: str,
    email: str,
    account_password: str,
    pinned_legacy_ca_pem: bytes,
    transport: Callable[[str, str, bytes], bytes],
    store: PrivateProfileStore,
) -> EnrollmentResult:
    """Transactional one-time enrollment using a *trusted injected* transport.

    transport(email, password, csr_pem) -> raw CA response; this callback is
    not provided here, preventing accidental live registrations.
    Credentials are only used during this invocation. A real RPC bridge must
    enforce authz, rate limits and replay protection around the caller.
    """
    hostname = remote_hostname(device_id)
    identity = normalize_email(email)
    if not isinstance(account_password, str) or not account_password:
        raise EnrollmentError("Missing account password")
    if not isinstance(pinned_legacy_ca_pem, bytes) or not pinned_legacy_ca_pem:
        raise TrustError("Missing independently verified legacy CA")
    if not callable(transport):
        raise EnrollmentError("Registration transport is unavailable")

    unlock_secret = secrets.token_urlsafe(36).encode("ascii")
    candidate = generate_candidate(identity, unlock_secret)
    try:
        # Sanitize exceptions: callback must not leak a password, CSR or
        # untrusted server response into logs or API errors.
        reply = transport(identity, account_password, candidate.csr_pem)
    except Exception:
        raise EnrollmentError("Certificate registration transport failed") from None
    cert = verify_trusted_registration_reply(reply, candidate, pinned_legacy_ca_pem)
    try:
        generation = store.commit(
            certificate_pem=cert.public_bytes(serialization.Encoding.PEM),
            encrypted_key_pem=candidate.key_pem_encrypted,
            unlock_secret=unlock_secret,
            identity=identity,
        )
    except (OSError, ValueError, StoreError):
        raise StoreError("Unable to commit authenticated identity") from None

    return EnrollmentResult(
        generation=generation,
        device_hostname=hostname,
        expires_at=cert.not_valid_after_utc.isoformat(),
    )
