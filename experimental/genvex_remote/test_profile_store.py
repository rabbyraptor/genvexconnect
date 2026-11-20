"""Offline filesystem tests: no real key material or Nabto service."""
from pathlib import Path
import json
import os
import stat
import tempfile
import unittest

from profile_store import PrivateProfileStore, StoreError


class ProfileStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "private-identity"
        self.store = PrivateProfileStore(self.root)

    def commit(self, name="device@example.org", key=b"encrypted-offline-key"):
        return self.store.commit(
            certificate_pem=b"-----BEGIN CERTIFICATE-----\nFAKE\n-----END CERTIFICATE-----",
            encrypted_key_pem=key, unlock_secret=b"long-fake-unlock-secret",
            identity=name,
        )

    def test_atomic_store_load_permissions(self):
        gen = self.commit()
        self.assertEqual(len(gen), 32)
        files = self.store.load()
        self.assertEqual(files["identity.txt"], b"device@example.org")
        self.assertEqual(files["client-encrypted.key"], b"encrypted-offline-key")
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.root / "active.json").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.root / "versions" / gen / "unlock.secret").stat().st_mode), 0o600)

    def test_second_version_is_atomic_pointer_switch(self):
        first = self.commit(key=b"first")
        second = self.commit(key=b"second")
        self.assertNotEqual(first, second)
        self.assertEqual(self.store.load()["client-encrypted.key"], b"second")
        self.assertEqual((self.root / "versions" / first / "client-encrypted.key").read_bytes(), b"first")

    def test_invalid_data_does_not_overwrite_active(self):
        self.commit(key=b"good")
        with self.assertRaises(StoreError):
            self.commit(key=b"")
        self.assertEqual(self.store.load()["client-encrypted.key"], b"good")

    def test_reject_insecure_root(self):
        self.root.mkdir()
        self.root.chmod(0o755)
        with self.assertRaises(StoreError):
            self.commit()

    def test_reject_root_symlink(self):
        target = Path(self.tmp.name) / "target"
        target.mkdir(mode=0o700)
        self.root.symlink_to(target, target_is_directory=True)
        with self.assertRaises(StoreError):
            self.commit()

    def test_reject_active_symlink(self):
        self.commit()
        pointer = self.root / "active.json"
        pointer.unlink()
        pointer.symlink_to(self.root / "versions")
        with self.assertRaises(StoreError):
            self.store.load()

    def test_reject_invalid_active_generation(self):
        self.commit()
        (self.root / "active.json").write_text(json.dumps({"generation": "../oops"}))
        with self.assertRaises(StoreError):
            self.store.load()

    def test_reject_world_readable_key(self):
        gen = self.commit()
        (self.root / "versions" / gen / "client-encrypted.key").chmod(0o644)
        with self.assertRaises(StoreError):
            self.store.load()

    def test_reject_path_or_malformed_identity(self):
        for value in ("../etc/passwd", "no-at-sign", "d@example.org\nX", "a@..invalid"):
            with self.subTest(identity=value):
                with self.assertRaises(StoreError):
                    self.commit(name=value)


if __name__ == "__main__":
    unittest.main()
