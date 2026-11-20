"""Offline service tests with an injected fake CA; never contacts LS Control."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from enrollment_core import EnrollmentError
from enrollment_service import enroll_with_transport
from profile_store import PrivateProfileStore


class OfflineRegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = datetime.now(timezone.utc)
        cls.ca_subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "offline-test-only-issuer")
        ])
        cls.ca_cert = (
            x509.CertificateBuilder().subject_name(cls.ca_subject)
            .issuer_name(cls.ca_subject).public_key(cls.ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=2))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(cls.ca_key, hashes.SHA256())
        )
        cls.ca_pem = cls.ca_cert.public_bytes(serialization.Encoding.PEM)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = PrivateProfileStore(Path(self.temporary.name) / "identity")

    def transport(self, email, password, csr_pem):
        self.assertEqual(email, "fake@example.org")
        self.assertEqual(password, "fake-account-secret")
        csr = x509.load_pem_x509_csr(csr_pem)
        self.assertTrue(csr.is_signature_valid)
        now = datetime.now(timezone.utc)
        issued = (
            x509.CertificateBuilder()
            .subject_name(csr.subject).issuer_name(self.ca_subject)
            .public_key(csr.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=2))
            .not_valid_after(now + timedelta(hours=24))
            .sign(self.ca_key, hashes.SHA256())
        )
        return b"0\nSuccess\n" + issued.public_bytes(serialization.Encoding.PEM)

    def enroll(self, transport=None):
        return enroll_with_transport(
            device_id="123456789012",
            email="fake@example.org",
            account_password="fake-account-secret",
            pinned_legacy_ca_pem=self.ca_pem,
            transport=transport or self.transport,
            store=self.store,
        )

    def test_end_to_end_fake_ca_and_atomic_store(self):
        result = self.enroll()
        self.assertEqual(result.device_hostname, "123456789012.remote.lscontrol.dk")
        self.assertEqual(len(result.generation), 32)
        profile = self.store.load()
        cert = x509.load_pem_x509_certificate(profile["client.crt"])
        private = serialization.load_pem_private_key(
            profile["client-encrypted.key"], profile["unlock.secret"],
        )
        self.assertEqual(cert.public_key().public_numbers(), private.public_key().public_numbers())
        self.assertEqual(private.key_size, 1024)

    def test_failing_transport_does_not_replace_existing(self):
        old = self.enroll()

        def unavailable(_email, _password, _csr):
            raise RuntimeError("untrusted upstream error body SECRET")

        with self.assertRaisesRegex(EnrollmentError, "transport failed") as context:
            self.enroll(transport=unavailable)
        self.assertNotIn("SECRET", str(context.exception))
        self.assertEqual(old.generation, self.store.load() and
                         __import__("json").loads((self.store.root / "active.json").read_text())["generation"])

    def test_invalid_registration_response_does_not_create_identity(self):
        with self.assertRaises(EnrollmentError):
            self.enroll(transport=lambda *_: b"1\nRejected")
        self.assertFalse((self.store.root / "active.json").exists())

    def test_invalid_device_id_aborts_before_network(self):
        def must_not_call(*_):
            raise AssertionError("Enrollment network was called")
        with self.assertRaises(ValueError):
            enroll_with_transport(
                device_id="not-a-device", email="fake@example.org",
                account_password="fake-account-secret",
                pinned_legacy_ca_pem=self.ca_pem,
                transport=must_not_call, store=self.store,
            )


if __name__ == "__main__":
    unittest.main()
