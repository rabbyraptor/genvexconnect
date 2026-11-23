"""Offline fake-CA tests; no live registration, credentials or network."""
from datetime import datetime, timedelta, timezone
import unittest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from certificate_trust import TrustError, verify_leaf_with_pinned_ca


def make_ca(common_name, ca=True):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(subject).issuer_name(subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now-timedelta(days=1))
            .not_valid_after(now+timedelta(days=2))
            .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    return key, cert


def make_leaf(ca_key, ca_cert, expired=False):
    key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "offline-leaf")]))
            .issuer_name(ca_cert.subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now-timedelta(days=3) if expired else now-timedelta(days=1))
            .not_valid_after(now-timedelta(days=2) if expired else now+timedelta(days=1))
            .sign(ca_key, hashes.SHA256()))
    return cert.public_bytes(serialization.Encoding.PEM)


class CertificateTrustTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ca_key, cls.ca_cert = make_ca("isolated-fake-CA")
        cls.ca = cls.ca_cert.public_bytes(serialization.Encoding.PEM)

    def test_valid_pinned_ca(self):
        leaf = make_leaf(self.ca_key, self.ca_cert)
        self.assertIsNotNone(verify_leaf_with_pinned_ca(leaf, self.ca))

    def test_wrong_ca(self):
        other_key, other_ca = make_ca("another-offline-CA")
        with self.assertRaises(TrustError):
            verify_leaf_with_pinned_ca(make_leaf(other_key, other_ca), self.ca)

    def test_same_name_different_key(self):
        other_key, other_ca = make_ca("isolated-fake-CA")
        with self.assertRaises(TrustError):
            verify_leaf_with_pinned_ca(make_leaf(other_key, other_ca), self.ca)

    def test_expired_leaf(self):
        with self.assertRaises(TrustError):
            verify_leaf_with_pinned_ca(make_leaf(self.ca_key, self.ca_cert, expired=True), self.ca)

    def test_non_ca(self):
        key, cert = make_ca("not-a-CA", ca=False)
        pem = cert.public_bytes(serialization.Encoding.PEM)
        with self.assertRaises(TrustError):
            verify_leaf_with_pinned_ca(make_leaf(key, cert), pem)

    def test_malformed(self):
        with self.assertRaises(TrustError):
            verify_leaf_with_pinned_ca(b"not a cert", self.ca)


if __name__ == "__main__":
    unittest.main()
