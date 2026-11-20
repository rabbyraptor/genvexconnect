"""Integration of key-match checks and explicitly pinned fake CA validation."""
from datetime import datetime, timedelta, timezone
import unittest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from certificate_trust import TrustError
from enrollment_core import (
    EnrollmentError, generate_candidate, verify_trusted_registration_reply
)


def issue_fake_certificate(key, candidate):
    now = datetime.now(timezone.utc)
    ca_subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "offline-unit-test-ca")])
    ca_cert = (x509.CertificateBuilder().subject_name(ca_subject)
               .issuer_name(ca_subject).public_key(key.public_key())
               .serial_number(x509.random_serial_number())
               .not_valid_before(now-timedelta(days=1))
               .not_valid_after(now+timedelta(days=1))
               .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
               .sign(key, hashes.SHA256()))
    leaf_cert = (x509.CertificateBuilder()
                 .subject_name(x509.Name([x509.NameAttribute(NameOID.EMAIL_ADDRESS, "offline@example.org")]))
                 .issuer_name(ca_subject)
                 .public_key(candidate.private_key.public_key())
                 .serial_number(x509.random_serial_number())
                 .not_valid_before(now-timedelta(hours=1))
                 .not_valid_after(now+timedelta(hours=1))
                 .sign(key, hashes.SHA256()))
    return (b"0\nSuccess\n" + leaf_cert.public_bytes(serialization.Encoding.PEM),
            ca_cert.public_bytes(serialization.Encoding.PEM))


class EnrollmentIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate = generate_candidate("offline@example.org", b"offline-test-16-byte-secret")
        cls.ca_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.reply, cls.anchor = issue_fake_certificate(cls.ca_private, cls.candidate)

    def test_valid_candidate_and_pinned_fake_ca(self):
        cert = verify_trusted_registration_reply(self.reply, self.candidate, self.anchor)
        self.assertEqual(cert.public_key().public_numbers(),
                         self.candidate.private_key.public_key().public_numbers())

    def test_rejects_different_fake_ca_even_same_subject(self):
        replacement_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        _reply, replacement_anchor = issue_fake_certificate(replacement_private, self.candidate)
        with self.assertRaises(TrustError):
            verify_trusted_registration_reply(self.reply, self.candidate, replacement_anchor)

    def test_rejects_wrong_candidate(self):
        wrong_candidate = generate_candidate("offline@example.org", b"another-offline-test-secret")
        with self.assertRaises(EnrollmentError):
            verify_trusted_registration_reply(self.reply, wrong_candidate, self.anchor)


if __name__ == "__main__":
    unittest.main()
