"""Tests of the offline, stdin-only private profile provisioning helper."""
from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import stat
import struct
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "runtime/profile_provision.py"
spec = importlib.util.spec_from_file_location("genvex_private_profile_provision", MODULE)
provisioner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provisioner)

CERT = b"-----BEGIN CERTIFICATE-----\nFAKE\n-----END CERTIFICATE-----\n"
KEY = (b"-----BEGIN ENCRYPTED PRIVATE KEY-----\nFAKE\n"
       b"-----END ENCRYPTED PRIVATE KEY-----\n")


def bundle(cert=CERT, key=KEY):
    return (struct.pack(">I", len(cert)) + cert +
            struct.pack(">I", len(key)) + key)


class ProvisioningTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.data = Path(temp.name) / "data"
        self.data.mkdir(mode=0o700)

    def test_import_creates_private_pem_pair(self):
        provisioner.provision(io.BytesIO(bundle()), data_dir=self.data)
        target = self.data / "profile"
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o700)
        for name, expected in (("client.crt", CERT),
                               ("client-encrypted.key", KEY)):
            path = target / name
            self.assertEqual(path.read_bytes(), expected)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertFalse(list(self.data.glob(".profile-stage-*")))

    def test_rejects_existing_profile_without_modification(self):
        provisioner.provision(io.BytesIO(bundle()), data_dir=self.data)
        with self.assertRaises(FileExistsError):
            provisioner.provision(io.BytesIO(bundle()), data_dir=self.data)
        self.assertEqual((self.data / "profile/client-encrypted.key").read_bytes(), KEY)

    def test_rejects_symlink_target(self):
        outside = self.data.parent / "outside"
        outside.mkdir()
        (self.data / "profile").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(FileExistsError):
            provisioner.provision(io.BytesIO(bundle()), data_dir=self.data)
        self.assertFalse(list(outside.iterdir()))

    def test_atomic_no_clobber_when_target_created_after_precheck(self):
        original = provisioner._rename_noreplace

        def competing_creator(parent_fd, staged, target):
            # Simulate another process creating an EMPTY directory after
            # the early existence check but before atomic publication.
            (self.data / "profile").mkdir(mode=0o700)
            original(parent_fd, staged, target)

        with patch.object(provisioner, "_rename_noreplace", competing_creator):
            with self.assertRaises(FileExistsError):
                provisioner.provision(io.BytesIO(bundle()), data_dir=self.data)
        self.assertEqual(list((self.data / "profile").iterdir()), [])
        self.assertFalse(list(self.data.glob(".profile-stage-*")))

    def test_atomic_no_clobber_when_target_symlink_created_during_promotion(self):
        original = provisioner._rename_noreplace
        outside = self.data.parent / "outside"
        outside.mkdir()

        def competing_symlink(parent_fd, staged, target):
            (self.data / "profile").symlink_to(outside, target_is_directory=True)
            original(parent_fd, staged, target)

        with patch.object(provisioner, "_rename_noreplace", competing_symlink):
            with self.assertRaises(FileExistsError):
                provisioner.provision(io.BytesIO(bundle()), data_dir=self.data)
        self.assertTrue((self.data / "profile").is_symlink())
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse(list(self.data.glob(".profile-stage-*")))

    def test_swapped_parent_path_does_not_publish_into_replacement(self):
        original = provisioner._rename_noreplace
        moved = self.data.parent / "original-data"
        impostor = self.data
        observed = {}

        def rename_under_swapped_parent(parent_fd, staged, target):
            # Simulate replacement of the visible /data directory after
            # staging; publication must stay on the originally checked inode.
            self.data.rename(moved)
            impostor.mkdir(mode=0o700)
            observed["old_inode"] = moved.stat().st_ino
            observed["fd_inode"] = provisioner.os.fstat(parent_fd).st_ino
            observed["replacement_inode"] = impostor.stat().st_ino
            original(parent_fd, staged, target)

        with patch.object(provisioner, "_rename_noreplace",
                          rename_under_swapped_parent):
            provisioner.provision(io.BytesIO(bundle()), data_dir=self.data)
        self.assertEqual(observed["fd_inode"], observed["old_inode"])
        self.assertNotEqual(observed["fd_inode"], observed["replacement_inode"])
        self.assertFalse((impostor / "profile").exists())
        self.assertTrue((moved / "profile/client-encrypted.key").is_file())
        self.assertFalse(list(moved.glob(".profile-stage-*")))

    def test_failure_cleanup_after_parent_path_swap(self):
        moved = self.data.parent / "original-data"
        original = provisioner._rename_noreplace

        def swapped_then_fail(parent_fd, staged, target):
            self.data.rename(moved)
            self.data.mkdir(mode=0o700)
            raise ValueError("Synthetic promotion failure")

        with patch.object(provisioner, "_rename_noreplace", swapped_then_fail):
            with self.assertRaisesRegex(ValueError, "Synthetic"):
                provisioner.provision(io.BytesIO(bundle()), data_dir=self.data)
        self.assertFalse((moved / "profile").exists())
        self.assertFalse(list(moved.glob(".profile-stage-*")))
        self.assertFalse((self.data / "profile").exists())

    def test_fail_closed_if_atomic_rename_unavailable(self):
        with patch.object(provisioner, "_rename_noreplace",
                          side_effect=ValueError("Atomic no-replace unsupported")):
            with self.assertRaises(ValueError):
                provisioner.provision(io.BytesIO(bundle()), data_dir=self.data)
        self.assertFalse((self.data / "profile").exists())
        self.assertFalse(list(self.data.glob(".profile-stage-*")))

    def test_rejects_truncated_payload(self):
        with self.assertRaises(ValueError):
            provisioner.provision(io.BytesIO(bundle()[:-7]), data_dir=self.data)
        self.assertFalse((self.data / "profile").exists())

    def test_rejects_trailing_data(self):
        with self.assertRaises(ValueError):
            provisioner.provision(io.BytesIO(bundle() + b"extra"), data_dir=self.data)
        self.assertFalse((self.data / "profile").exists())

    def test_rejects_invalid_envelope(self):
        with self.assertRaises(ValueError):
            provisioner.provision(io.BytesIO(bundle(key=b"plain key")), data_dir=self.data)
        self.assertFalse((self.data / "profile").exists())

    def test_rejects_oversize_length_without_reading_payload(self):
        stream = io.BytesIO(struct.pack(">I", provisioner.MAX_PEM + 1))
        with self.assertRaises(ValueError):
            provisioner.provision(stream, data_dir=self.data)

    def test_rejects_world_writable_data_dir(self):
        self.data.chmod(0o777)
        with self.assertRaises(ValueError):
            provisioner.provision(io.BytesIO(bundle()), data_dir=self.data)

    def test_rejects_group_or_other_writable_data_dir(self):
        for mode in (0o770, 0o775, 0o777, 0o722, 0o702):
            with self.subTest(mode=oct(mode)):
                self.data.chmod(mode)
                with self.assertRaises(ValueError):
                    provisioner.provision(io.BytesIO(bundle()), data_dir=self.data)
                self.assertFalse((self.data / "profile").exists())
        self.data.chmod(0o700)

    def test_supervisor_0755_data_dir_still_creates_private_profile(self):
        self.data.chmod(0o755)
        provisioner.provision(io.BytesIO(bundle()), data_dir=self.data)
        self.assertEqual(stat.S_IMODE(self.data.stat().st_mode), 0o755)
        target = self.data / "profile"
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o700)
        for name in (provisioner.CERT_NAME, provisioner.KEY_NAME):
            self.assertEqual(stat.S_IMODE((target / name).stat().st_mode), 0o600)

    def test_owner_read_only_permissions_can_be_non_private(self):
        for mode in (0o750, 0o705):
            with self.subTest(mode=oct(mode)):
                temp = tempfile.TemporaryDirectory()
                self.addCleanup(temp.cleanup)
                root = Path(temp.name) / "data"
                root.mkdir(mode=0o700)
                root.chmod(mode)
                provisioner.provision(io.BytesIO(bundle()), data_dir=root)
                self.assertEqual(stat.S_IMODE((root / "profile").stat().st_mode), 0o700)

    def test_rejects_data_dir_owned_by_different_identity(self):
        with patch.object(provisioner.os, "geteuid",
                          return_value=self.data.stat().st_uid + 1):
            with self.assertRaises(ValueError):
                provisioner.provision(io.BytesIO(bundle()), data_dir=self.data)
        self.assertFalse((self.data / "profile").exists())

    def test_rejects_dangling_profile_symlink(self):
        (self.data / "profile").symlink_to(self.data / "missing", target_is_directory=True)
        with self.assertRaises(FileExistsError):
            provisioner.provision(io.BytesIO(bundle()), data_dir=self.data)
        self.assertTrue((self.data / "profile").is_symlink())
        self.assertFalse(list(self.data.glob(".profile-stage-*")))

    def test_rejects_symlink_data_dir(self):
        alias = self.data.parent / "alias"
        alias.symlink_to(self.data, target_is_directory=True)
        with self.assertRaises(ValueError):
            provisioner.provision(io.BytesIO(bundle()), data_dir=alias)

    def test_no_partial_profile_after_invalid_input(self):
        with self.assertRaises(ValueError):
            provisioner.provision(io.BytesIO(bundle(cert=b"invalid")), data_dir=self.data)
        self.assertEqual(list(self.data.iterdir()), [])


    def test_provisioned_profile_passes_app_bootstrap_validation(self):
        # Exercise the exact handoff between the provisioner and the App.
        import sys
        sys.path.insert(0, str(MODULE.parent))
        import app_bootstrap
        provisioner.provision(io.BytesIO(bundle()), data_dir=self.data)
        app_bootstrap.validate_private_profile(self.data / "profile")

    def test_app_rejects_swapped_certificate_and_key(self):
        import sys
        sys.path.insert(0, str(MODULE.parent))
        import app_bootstrap
        provisioner.provision(io.BytesIO(bundle()), data_dir=self.data)
        cert = self.data / "profile/client.crt"
        key = self.data / "profile/client-encrypted.key"
        cert_bytes, key_bytes = cert.read_bytes(), key.read_bytes()
        cert.write_bytes(key_bytes)
        key.write_bytes(cert_bytes)
        with self.assertRaises(ValueError):
            app_bootstrap.validate_private_profile(self.data / "profile")

    def test_app_rejects_unencrypted_private_key(self):
        import sys
        sys.path.insert(0, str(MODULE.parent))
        import app_bootstrap
        provisioner.provision(io.BytesIO(bundle()), data_dir=self.data)
        key = self.data / "profile/client-encrypted.key"
        key.write_bytes(b"-----BEGIN PRIVATE KEY-----\\nFAKE\\n-----END PRIVATE KEY-----\\n")
        with self.assertRaises(ValueError):
            app_bootstrap.validate_private_profile(self.data / "profile")


if __name__ == "__main__":
    unittest.main()
