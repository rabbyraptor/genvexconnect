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

    def test_short_poll_interval_rejected(self):
        self.opts["poll_seconds"] = 5
        self.opt_path.write_text(json.dumps(self.opts))
        with self.assertRaises(ValueError):
            app.read_options(self.opt_path)

    def test_profile_copied_to_private_permissions(self):
        app.prepare_private_profile(self.src, self.dst)
        for name in ("client.crt", "client-encrypted.key"):
            target = self.dst / name
            self.assertEqual(target.read_bytes(), (self.src / name).read_bytes())
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.dst.stat().st_mode), 0o700)

    def test_symlink_profile_file_rejected(self):
        (self.src / "client.crt").unlink()
        (self.src / "client.crt").symlink_to(self.src / "client-encrypted.key")
        with self.assertRaises(ValueError):
            app.prepare_private_profile(self.src, self.dst)

    def test_token_written_private(self):
        dest = self.root / "ipc-token"
        app.write_token(self.opts["ipc_token"], dest)
        self.assertEqual(dest.read_text().strip(), self.opts["ipc_token"])
        self.assertEqual(stat.S_IMODE(dest.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
