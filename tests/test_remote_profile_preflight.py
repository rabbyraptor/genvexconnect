"""Offline tests for read-only F2 profile preflight; fake PEM only."""
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "remote_profile_preflight.py"
spec = importlib.util.spec_from_file_location("remote_profile_preflight", MODULE)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)

CERT = b"-----BEGIN CERTIFICATE-----\nZmFrZQ==\n-----END CERTIFICATE-----\n"
KEY = (b"-----BEGIN ENCRYPTED PRIVATE KEY-----\nZmFrZQ==\n"
       b"-----END ENCRYPTED PRIVATE KEY-----\n")


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.src = self.root / "source"
        self.src.mkdir(mode=0o700)
        self.dest = self.root / "destination"
        self.cert = self.src / "client.crt"
        self.key = self.src / "client-encrypted.key"
        self.cert.write_bytes(CERT)
        self.key.write_bytes(KEY)
        self.cert.chmod(0o600)
        self.key.chmod(0o600)

    def test_valid_fake_profile_read_only(self):
        preflight.plan(self.src, self.dest)
        self.assertFalse(self.dest.exists())
        self.assertEqual(self.cert.read_bytes(), CERT)
        self.assertEqual(self.key.read_bytes(), KEY)

    def test_missing_source(self):
        with self.assertRaises(OSError):
            preflight.plan(self.root / "missing", self.dest)

    def test_missing_file(self):
        self.key.unlink()
        with self.assertRaises(OSError):
            preflight.plan(self.src, self.dest)

    def test_malformed_pem(self):
        self.key.write_bytes(b"not a PEM")
        with self.assertRaises(preflight.ProfilePreflightError):
            preflight.plan(self.src, self.dest)

    def test_oversize(self):
        self.cert.write_bytes(b"x" * (preflight.MAX_BYTES + 1))
        with self.assertRaises(preflight.ProfilePreflightError):
            preflight.plan(self.src, self.dest)

    def test_symlink_file(self):
        self.key.unlink()
        self.key.symlink_to(self.cert)
        with self.assertRaises(OSError):
            preflight.plan(self.src, self.dest)

    def test_symlink_directory(self):
        link = self.root / "linked"
        link.symlink_to(self.src, target_is_directory=True)
        with self.assertRaises(preflight.ProfilePreflightError):
            preflight.plan(link, self.dest)

    def test_world_readable_source_file(self):
        self.key.chmod(0o644)
        with self.assertRaises(preflight.ProfilePreflightError):
            preflight.plan(self.src, self.dest)

    def test_world_readable_source_directory(self):
        self.src.chmod(0o755)
        with self.assertRaises(preflight.ProfilePreflightError):
            preflight.plan(self.src, self.dest)

    def test_existing_destination(self):
        self.dest.mkdir()
        with self.assertRaises(preflight.ProfilePreflightError):
            preflight.plan(self.src, self.dest)

    def test_dangling_destination_symlink(self):
        self.dest.symlink_to(self.root / "missing")
        with self.assertRaises(preflight.ProfilePreflightError):
            preflight.plan(self.src, self.dest)

    def test_repeated_checks_do_not_create_files(self):
        for _ in range(2):
            preflight.plan(self.src, self.dest)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["source"])

    def test_no_secret_output(self):
        output = io.StringIO()
        with redirect_stdout(output):
            preflight.plan(self.src, self.dest)
        self.assertNotIn("ZmFrZQ", output.getvalue())
        self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
