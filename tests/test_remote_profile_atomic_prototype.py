"""Synthetic-only tests for F2.3 prototype. No real Nabto material."""
import importlib.util
import multiprocessing
from pathlib import Path
import stat
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / "scripts" / "remote_profile_atomic_prototype.py"
spec = importlib.util.spec_from_file_location("remote_profile_atomic_prototype", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _attempt(root: str, ready, go, results):
    ready.put(1)
    go.wait(5)
    try:
        mod.simulate_atomic_import(Path(root))
        results.put("success")
    except (OSError, mod.PrototypeError):
        results.put("rejected")


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
            path = dest / name
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(dest.stat().st_mode), 0o700)
        self.assertTrue((self.root / ".test-lock").exists())

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

    def test_competing_destination_created_during_staging(self):
        def competing(root):
            dest = root / "profile"
            dest.mkdir(mode=0o700)
            (dest / "sentinel").write_text("keep")
        with self.assertRaises(mod.PrototypeError):
            mod.simulate_atomic_import(self.root, before_promote=competing)
        self.assertEqual((self.root / "profile" / "sentinel").read_text(), "keep")
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["profile"])

    def test_competing_empty_destination_not_replaced(self):
        def competing(root):
            (root / "profile").mkdir(mode=0o700)
        with self.assertRaises(mod.PrototypeError):
            mod.simulate_atomic_import(self.root, before_promote=competing)
        self.assertEqual(list((self.root / "profile").iterdir()), [])
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["profile"])

    def test_competing_symlink_destination_not_replaced(self):
        external = self.root.parent / (self.root.name + "-external")
        external.mkdir()
        self.addCleanup(external.rmdir)
        def competing(root):
            (root / "profile").symlink_to(external, target_is_directory=True)
        with self.assertRaises(mod.PrototypeError):
            mod.simulate_atomic_import(self.root, before_promote=competing)
        self.assertTrue((self.root / "profile").is_symlink())
        self.assertEqual(list(external.iterdir()), [])
        (self.root / "profile").unlink()

    def test_two_processes_exactly_one_success(self):
        ctx = multiprocessing.get_context("fork")
        ready = ctx.Queue()
        go = ctx.Event()
        results = ctx.Queue()
        processes = [ctx.Process(target=_attempt, args=(str(self.root), ready, go, results)) for _ in range(2)]
        try:
            for proc in processes:
                proc.start()
            for _ in processes:
                self.assertEqual(ready.get(timeout=5), 1)
            go.set()
            for proc in processes:
                proc.join(10)
                self.assertFalse(proc.is_alive())
                self.assertEqual(proc.exitcode, 0)
            self.assertEqual(sorted([results.get(timeout=3) for _ in processes]),
                             ["rejected", "success"])
            self.assertEqual((self.root / "profile" / "client.crt").read_bytes(), mod.FAKE_CERT)
        finally:
            go.set()
            for proc in processes:
                if proc.is_alive():
                    proc.terminate()
                proc.join(timeout=2)

    def test_no_fallback_when_rename_unavailable(self):
        original = mod._rename_noreplace
        def unsupported(*args):
            raise mod.PrototypeError("Atomic no-replace unsupported")
        mod._rename_noreplace = unsupported
        try:
            with self.assertRaises(mod.PrototypeError):
                mod.simulate_atomic_import(self.root)
            self.assertEqual(list(self.root.iterdir()), [])
        finally:
            mod._rename_noreplace = original


if __name__ == "__main__":
    unittest.main()
