"""Offline-only legacy certificate enrollment primitives. No HTTP or filesystem writes.

Legacy RSA-1024 is obsolete. Candidate key uses the exact OpenSSL PKCS8/PBES2
parameters proven for an older working test profile; the newly generated key
has NOT yet been exercised against Nabto SDK 4.9.11: do not auto-install.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parseaddr
import re

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from sdk_compat import encrypt_legacy_pkcs8

_CERT_PATTERN = re.compile(
    rb"-----BEGIN CERTIFICATE-----\s+.+?\s+-----END CERTIFICATE-----", re.DOTALL
)


class EnrollmentError(Exception):
    """Sanitized error; do not expose vendor response bodies."""


@dataclass(frozen=True)
class EnrollmentMaterial:
    csr_pem: bytes
    key_pem_encrypted: bytes
    private_key: rsa.RSAPrivateKey


def normalize_email(email: str) -> str:
    if not isinstance(email, str) or len(email) > 254 or email != email.strip():
        raise EnrollmentError("Invalid account identity")
    realname, parsed = parseaddr(email)
    if realname or parsed != email or email.count("@") != 1:
        raise EnrollmentError("Invalid account identity")
    local, domain = email.rsplit("@", 1)
    if not local or not domain or "." not in domain or not email.isascii():
        raise EnrollmentError("Invalid account identity")
    if any(ord(ch) <= 32 or ord(ch) >= 127 or ch in '<>\\"\'' for ch in email):
        raise EnrollmentError("Invalid account identity")
    return email


def generate_candidate(email: str, key_passphrase: bytes) -> EnrollmentMaterial:
    """Generate RSA-1024 CSR and legacy-compatible encrypted PKCS8 candidate."""
    email = normalize_email(email)
    if not isinstance(key_passphrase, bytes) or len(key_passphrase) < 16:
        raise EnrollmentError("A sufficiently long unlock secret is required")
    key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.EMAIL_ADDRESS, email)]))
        .sign(key, hashes.SHA256())
    )
    return EnrollmentMaterial(
        csr_pem=csr.public_bytes(serialization.Encoding.PEM),
        key_pem_encrypted=encrypt_legacy_pkcs8(key, key_passphrase),
        private_key=key,
    )


def verify_registration_reply(response: bytes, candidate: EnrollmentMaterial) -> x509.Certificate:
    """Parse observed LS Control CA response and check key/validity, NOT CA trust."""
    if not isinstance(response, bytes) or len(response) > 65536:
        raise EnrollmentError("Certificate enrollment failed")
    if response.split(b"\n", 1)[0].strip() != b"0":
        raise EnrollmentError("Certificate enrollment rejected")
    matches = _CERT_PATTERN.findall(response)
    if len(matches) != 1:
        raise EnrollmentError("Invalid enrollment certificate response")
    try:
        cert = x509.load_pem_x509_certificate(matches[0])
        public = cert.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        original = candidate.private_key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        if public != original:
            raise EnrollmentError("Certificate does not match generated key")
        now = datetime.now(timezone.utc)
        if not cert.not_valid_before_utc <= now < cert.not_valid_after_utc:
            raise EnrollmentError("Certificate is not currently valid")
        return cert
    except (ValueError, TypeError):
        raise EnrollmentError("Invalid enrollment certificate response") from None
