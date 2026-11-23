"""Offline, fake-credential checks for the separate App bootstrap (no HAOS)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1] / "runtime"
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("genvex_app_bootstrap", HERE / "app_bootstrap.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.opts = {
            "device_id": "123456789012",
            "identity": "user@example.invalid",
            "unlock_secret": "fake-password-only",
            "ipc_token": "A" * 43,
            "poll_seconds": 60,
        }
        self.opt_path = self.root / "options.json"
        self.opt_path.write_text(json.dumps(self.opts))
        self.src = self.root / "source"
        self.dst = self.root / "private"
        self.src.mkdir()
        (self.src / "client.crt").write_text(
            "-----BEGIN CERTIFICATE-----\nFAKE\n-----END CERTIFICATE-----\n"
        )
        (self.src / "client-encrypted.key").write_text(
            "-----BEGIN ENCRYPTED PRIVATE KEY-----\nFAKE\n-----END ENCRYPTED PRIVATE KEY-----\n"
        )

    def test_valid_options(self):
        self.assertEqual(app.read_options(self.opt_path)["device_id"], "123456789012")

    def test_bad_token(self):
        self.opts["ipc_token"] = "short"
        self.opt_path.write_text(json.dumps(self.opts))
        with self.assertRaises(Exception):
            app.read_options(self.opt_path)

    def test_invalid_identity_and_secret(self):
        for key in ("identity", "unlock_secret"):
            with self.subTest(key=key):
                opts = dict(self.opts)
                opts[key] = "line\nsecret"
                self.opt_path.write_text(json.dumps(opts))
                with self.assertRaises(ValueError):
                    app.read_options(self.opt_path)

    def test_persistent_session_opt_in_is_strict_boolean(self):
        for value in (True, False):
            with self.subTest(value=value):
                self.opts["persistent_session"] = value
                self.opt_path.write_text(json.dumps(self.opts))
                self.assertEqual(app.read_options(self.opt_path)["persistent_session"], value)
        for value in ("true", 1, None):
            with self.subTest(invalid=value):
                self.opts["persistent_session"] = value
                self.opt_path.write_text(json.dumps(self.opts))
                with self.assertRaises(ValueError):
                    app.read_options(self.opt_path)

    def test_diagnostic_and_persistent_are_mutually_exclusive(self):
        self.opts = {"diagnostic_only": True, "persistent_session": True}
        self.opt_path.write_text(json.dumps(self.opts))
        with self.assertRaises(ValueError):
            app.read_options(self.opt_path)

    def test_short_poll_interval_rejected(self):
        self.opts["poll_seconds"] = 5
        self.opt_path.write_text(json.dumps(self.opts))
        with self.assertRaises(ValueError):
            app.read_options(self.opt_path)

    def _create_private_profile(self):
        self.dst.mkdir(mode=0o700)
        for name in ("client.crt", "client-encrypted.key"):
            target = self.dst / name
            target.write_bytes((self.src / name).read_bytes())
            target.chmod(0o600)

    def test_valid_private_profile(self):
        self._create_private_profile()
        app.validate_private_profile(self.dst)

    def test_missing_profile_rejected(self):
        with self.assertRaises(FileNotFoundError):
            app.validate_private_profile(self.dst)

    def test_shared_source_not_imported(self):
        # Existing /share source is never consulted or copied.
        with self.assertRaises(FileNotFoundError):
            app.validate_private_profile(self.dst)
        self.assertFalse(self.dst.exists())

    def test_insecure_directory_rejected(self):
        self._create_private_profile()
        self.dst.chmod(0o755)
        with self.assertRaises(ValueError):
            app.validate_private_profile(self.dst)

    def test_insecure_key_permissions_rejected(self):
        self._create_private_profile()
        (self.dst / "client-encrypted.key").chmod(0o644)
        with self.assertRaises(ValueError):
            app.validate_private_profile(self.dst)

    def test_symlink_profile_file_rejected(self):
        self._create_private_profile()
        (self.dst / "client.crt").unlink()
        (self.dst / "client.crt").symlink_to(self.dst / "client-encrypted.key")
        with self.assertRaises(OSError):
            app.validate_private_profile(self.dst)

    def test_symlink_profile_directory_rejected(self):
        self._create_private_profile()
        link = self.root / "linked-profile"
        link.symlink_to(self.dst, target_is_directory=True)
        with self.assertRaises(ValueError):
            app.validate_private_profile(link)

    def test_malformed_private_key_rejected(self):
        self._create_private_profile()
        (self.dst / "client-encrypted.key").write_text("not a PEM")
        with self.assertRaises(ValueError):
            app.validate_private_profile(self.dst)

    def test_token_written_private(self):
        dest = self.root / "ipc-token"
        app.write_token(self.opts["ipc_token"], dest)
        self.assertEqual(dest.read_text().strip(), self.opts["ipc_token"])
        self.assertEqual(stat.S_IMODE(dest.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
