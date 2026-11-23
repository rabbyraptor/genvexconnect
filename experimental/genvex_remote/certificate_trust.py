"""Offline X.509 signature verification against a separately pinned legacy CA.

The trusted CA certificate MUST be obtained and verified independently.
Only direct issuer signatures are supported; no trust-on-first-use or
system-wide CA fallback. Intermediates require additional reviewed logic.
"""
from __future__ import annotations
from datetime import datetime, timezone
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.x509.oid import ExtensionOID


class TrustError(Exception):
    """Fixed failure description; do not expose certificate content."""


def verify_leaf_with_pinned_ca(
    leaf_pem: bytes, trusted_ca_pem: bytes, *, now: datetime | None = None
) -> x509.Certificate:
    """Validate leaf issuer, CA permission, time window and CA signature."""
    if (not isinstance(leaf_pem, bytes) or not isinstance(trusted_ca_pem, bytes)
            or len(leaf_pem) > 32768 or len(trusted_ca_pem) > 32768):
        raise TrustError("Invalid certificate inputs")
    try:
        leaf = x509.load_pem_x509_certificate(leaf_pem)
        ca = x509.load_pem_x509_certificate(trusted_ca_pem)
        if leaf.issuer != ca.subject:
            raise TrustError("Certificate issuer does not match the trusted CA")
        constraints = ca.extensions.get_extension_for_oid(
            ExtensionOID.BASIC_CONSTRAINTS
        ).value
        if not constraints.ca:
            raise TrustError("Trusted signer is not a CA")
        try:
            usage = ca.extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE).value
        except x509.ExtensionNotFound:
            usage = None
        if usage is not None and not usage.key_cert_sign:
            raise TrustError("Trusted signer cannot sign certificates")
        now = now or datetime.now(timezone.utc)
        if not leaf.not_valid_before_utc <= now < leaf.not_valid_after_utc:
            raise TrustError("Certificate is expired or not yet valid")
        if not ca.not_valid_before_utc <= now < ca.not_valid_after_utc:
            raise TrustError("Trusted CA validity period failed")
        public = ca.public_key()
        if isinstance(public, rsa.RSAPublicKey):
            public.verify(
                leaf.signature, leaf.tbs_certificate_bytes,
                padding.PKCS1v15(), leaf.signature_hash_algorithm,
            )
        elif isinstance(public, ec.EllipticCurvePublicKey):
            public.verify(
                leaf.signature, leaf.tbs_certificate_bytes,
                ec.ECDSA(leaf.signature_hash_algorithm),
            )
        else:
            raise TrustError("Unsupported legacy CA signing key")
        return leaf
    except TrustError:
        raise
    except (ValueError, TypeError, x509.ExtensionNotFound,
            InvalidSignature, AttributeError, OverflowError):
        raise TrustError("Certificate trust validation failed") from None
