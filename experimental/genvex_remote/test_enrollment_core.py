"""Offline enrollment checks; no vendor requests, key files or live account access."""
from datetime import datetime, timedelta, timezone
import unittest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from enrollment_core import EnrollmentError, generate_candidate, normalize_email, verify_registration_reply


def fake_ca_reply(key, days=2):
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Fake offline leaf")]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Fake offline CA")]))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=days))
        .sign(key, hashes.SHA256())
    )
    return b"0\nSuccess\n" + certificate.public_bytes(serialization.Encoding.PEM)


class EnrollmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate = generate_candidate("test@example.org", b"offline-secret-only-for-tests")

    def test_key_encrypted_and_csr_matching(self):
        pem = self.candidate.key_pem_encrypted
        self.assertIn(b"ENCRYPTED PRIVATE KEY", pem)
        self.assertNotIn(b"BEGIN RSA PRIVATE KEY", pem)
        key = serialization.load_pem_private_key(pem, b"offline-secret-only-for-tests")
        csr = x509.load_pem_x509_csr(self.candidate.csr_pem)
        self.assertTrue(csr.is_signature_valid)
        self.assertEqual(csr.subject.get_attributes_for_oid(NameOID.EMAIL_ADDRESS)[0].value, "test@example.org")
        self.assertEqual(key.key_size, 1024)

    def test_accepts_valid_matching_cert(self):
        cert = verify_registration_reply(fake_ca_reply(self.candidate.private_key), self.candidate)
        self.assertEqual(cert.public_key().key_size, 1024)

    def test_rejects_mismatch(self):
        different = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        with self.assertRaises(EnrollmentError):
            verify_registration_reply(fake_ca_reply(different), self.candidate)

    def test_rejects_expiry(self):
        with self.assertRaises(EnrollmentError):
            verify_registration_reply(fake_ca_reply(self.candidate.private_key, days=0), self.candidate)

    def test_rejects_bad_provider_replies(self):
        for raw in (b"1\nBad credentials", b"0\nSuccess\n", b"", b"0\n" + b"x" * 65536):
            with self.subTest(size=len(raw)):
                with self.assertRaises(EnrollmentError):
                    verify_registration_reply(raw, self.candidate)

    def test_rejects_malformed_email(self):
        for address in ("", "foo", " test@example.org", "A <test@example.org>", "test@example.org\nInjected", "test@local"):
            with self.subTest(address=address):
                with self.assertRaises(EnrollmentError):
                    normalize_email(address)


if __name__ == "__main__":
    unittest.main()
