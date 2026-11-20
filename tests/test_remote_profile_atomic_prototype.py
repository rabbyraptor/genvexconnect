"""Synthetic-only tests for F2.2 prototype. No real Nabto material."""
import importlib.util
import os
from pathlib import Path
import stat
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / "scripts" / "remote_profile_atomic_prototype.py"
spec = importlib.util.spec_from_file_location("remote_profile_atomic_prototype", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class AtomicPrototypeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)

    def test_fake_profile_promoted(self):
        dest = mod.simulate_atomic_import(self.root)
        self.assertEqual(dest.name, "profile")
        self.assertEqual(sorted(p.name for p in dest.iterdir()), sorted(mod.FIXTURES))
        for name, data in mod.FIXTURES.items():
            file = dest / name
            self.assertEqual(file.read_bytes(), data)
            self.assertEqual(stat.S_IMODE(file.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(dest.stat().st_mode), 0o700)
        self.assertFalse((self.root / ".test-lock").exists())

    def test_rollback_before_first_file(self):
        with self.assertRaises(mod.PrototypeError):
            mod.simulate_atomic_import(self.root, fail_after=0)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_rollback_after_first_file(self):
        with self.assertRaises(mod.PrototypeError):
            mod.simulate_atomic_import(self.root, fail_after=1)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_reject_nonempty_root(self):
        (self.root / "sentinel").write_text("untouched")
        with self.assertRaises(mod.PrototypeError):
            mod.simulate_atomic_import(self.root)
        self.assertEqual((self.root / "sentinel").read_text(), "untouched")

    def test_reject_symlink_root(self):
        link = self.root.parent / (self.root.name + "-link")
        link.symlink_to(self.root, target_is_directory=True)
        self.addCleanup(link.unlink)
        with self.assertRaises(mod.PrototypeError):
            mod.simulate_atomic_import(link)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_reject_world_readable_root(self):
        self.root.chmod(0o755)
        with self.assertRaises(mod.PrototypeError):
            mod.simulate_atomic_import(self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_no_repeat_overwrite(self):
        dest = mod.simulate_atomic_import(self.root)
        with self.assertRaises(mod.PrototypeError):
            mod.simulate_atomic_import(self.root)
        self.assertEqual((dest / "client.crt").read_bytes(), mod.FAKE_CERT)


if __name__ == "__main__":
    unittest.main()
