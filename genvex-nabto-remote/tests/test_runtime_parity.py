"""Offline checks for canonical runtime/source parity (no external services)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "scripts/check_remote_runtime_parity.py"
spec = importlib.util.spec_from_file_location("runtime_parity", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class RuntimeParityTests(unittest.TestCase):
    def test_real_checked_in_sources_match(self):
        self.assertEqual(mod.check(), [])

    def test_drift_and_explicit_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "source"
            app = root / "app"
            src.mkdir()
            app.mkdir()
            (src / "polling_service.py").write_text("canonical\n")
            (app / "polling_service.py").write_text("old\n")
            (app / "app_bootstrap.py").write_text("app-only\n")
            self.assertEqual(mod.check(src, app), ["polling_service.py"])
            self.assertEqual(mod.sync(src, app), ["polling_service.py"])
            self.assertEqual(mod.check(src, app), [])
            self.assertEqual(mod.sync(src, app), [])
            self.assertEqual((app / "app_bootstrap.py").read_text(), "app-only\n")

    def test_missing_canonical_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "source"
            app = root / "app"
            src.mkdir()
            app.mkdir()
            (app / "snapshot_contract.py").write_text("placeholder")
            with self.assertRaises(ValueError):
                mod.check(src, app)


if __name__ == "__main__":
    unittest.main()
