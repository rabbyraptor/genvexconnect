"""Tests for exact previously observed OpenSSL/PBES2 key format."""
import subprocess
import unittest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sdk_compat import KeyFormatError, encrypt_legacy_pkcs8


class SDKCompatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=1024)

    def test_encrypt_decrypt_matches(self):
        pw = b"this-is-only-a-test-key-unlock-secret"
        pem = encrypt_legacy_pkcs8(self.key, pw)
        loaded = serialization.load_pem_private_key(pem, pw)
        self.assertEqual(loaded.private_numbers(), self.key.private_numbers())
        self.assertIn(b"ENCRYPTED PRIVATE KEY", pem)

    def test_asn1_pbes2_3des_sha256_and_iterations(self):
        pem = encrypt_legacy_pkcs8(self.key, b"another-offline-passphrase")
        result = subprocess.run(
            ["openssl", "asn1parse", "-inform", "PEM"],
            input=pem, capture_output=True, check=True,
        )
        dump = result.stdout.decode()
        self.assertIn("PBES2", dump)
        self.assertIn("PBKDF2", dump)
        self.assertIn("hmacWithSHA256", dump)
        self.assertIn("des-ede3-cbc", dump)
        self.assertIn(":0800", dump)  # ASN.1 hex 0x0800 = 2048 iterations

    def test_reject_weak_passphrase(self):
        for pw in (b"", b"abc", b"bad\nsecret-with-newline", b"\0" * 20):
            with self.subTest(length=len(pw)):
                with self.assertRaises(KeyFormatError):
                    encrypt_legacy_pkcs8(self.key, pw)

    def test_reject_other_key_sizes(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with self.assertRaises(KeyFormatError):
            encrypt_legacy_pkcs8(key, b"this-secret-is-long-enough")


if __name__ == "__main__":
    unittest.main()
