"""Offline source baseline invariants: no HAOS required."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
spec = importlib.util.spec_from_file_location(
    "dev4_preflight", Path(__file__).resolve().parents[2] / "scripts" / "dev4_source_baseline_preflight.py"
)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class Dev4SourceBaselineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "runtime").mkdir()
        self.data = b"test source file\n"
        (self.root / "runtime" / "worker.py").write_bytes(self.data)
        self.expected = {
            "runtime/worker.py": [
                hashlib.sha1(b"blob " + str(len(self.data)).encode() + b"\0" + self.data).hexdigest(),
                len(self.data),
            ],
        }

    def test_exact_source_matches(self):
        self.assertEqual(gate.verify_source_tree(self.root, self.expected), 1)

    def test_extra_file_rejected(self):
        (self.root / "unexpected.py").write_text("extra")
        with self.assertRaises(gate.PreflightError):
            gate.verify_source_tree(self.root, self.expected)

    def test_changed_source_rejected(self):
        (self.root / "runtime" / "worker.py").write_bytes(b"changed")
        with self.assertRaises(gate.PreflightError):
            gate.verify_source_tree(self.root, self.expected)

    def test_symlink_rejected(self):
        (self.root / "runtime" / "worker.py").unlink()
        (self.root / "runtime" / "worker.py").symlink_to(self.root / "missing")
        with self.assertRaises(gate.PreflightError):
            gate.verify_source_tree(self.root, self.expected)

    def test_unexpected_subdirectory_rejected(self):
        (self.root / "newdir").mkdir()
        with self.assertRaises(gate.PreflightError):
            gate.verify_source_tree(self.root, self.expected)

    def test_baseline_manifest_has_23_pinned_files(self):
        self.assertEqual(len(gate.EXPECTED), 23)
        self.assertEqual(
            gate.BASELINE_COMMIT, "d7ad38a60991cca1a4f4b3af677ee501d749f74c"
        )
        self.assertIn("runtime/sdk_snapshot_adapter.py", gate.EXPECTED)
        self.assertIn("runtime/polling_runtime.py", gate.EXPECTED)
        self.assertIn("config.yaml", gate.EXPECTED)


if __name__ == "__main__":
    unittest.main()
