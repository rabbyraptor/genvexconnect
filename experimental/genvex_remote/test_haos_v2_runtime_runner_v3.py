"""Guard pinned HAOS v2 runtime offline test runner against staging regression."""
from __future__ import annotations

from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/archive/run_haos_v2_runtime_offline_v3.sh"
PINNED = "c47cec979755ba20d99521cb5a5081283d4b0b45"


class V3RuntimeRunnerTests(unittest.TestCase):
    def test_syntax_and_preview_no_container_ops(self):
        result = subprocess.run(
            ["sh", "-n", str(SCRIPT)], capture_output=True,
            text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run(
            ["sh", str(SCRIPT), "--preflight"], capture_output=True,
            text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("V2 RUNTIME OFFLINE PREFLIGHT v3", result.stdout)
        self.assertIn("no container/network operations", result.stdout)
        self.assertIn(PINNED, result.stdout)

    def test_explicit_offline_mode_only(self):
        for params in ([], ["--execute-live"], ["--execute-offline", "--preflight"]):
            with self.subTest(params=params):
                result = subprocess.run(
                    ["sh", str(SCRIPT), *params],
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 2)

    def test_full_repo_layout_and_v2_dependency_checks(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(PINNED, source)
        self.assertIn(
            "experimental/genvex_remote experimental/home_assistant scripts",
            source,
        )
        self.assertIn("sdk_snapshot_adapter_v2.py", source)
        self.assertIn("probe_remote_snapshot_v2.py", source)
        self.assertIn("runtime_v2_draft.py", source)
        self.assertIn("test_sdk_snapshot_adapter_v2.py", source)
        self.assertIn("test_runtime_v2_draft.py", source)
        self.assertIn("python3 -m unittest discover", source)
        self.assertNotIn("docker cp", source)
        self.assertNotIn("nabtoRpcInvoke", source)
        self.assertNotIn("unlock_secret", source)
        self.assertNotIn("profile_dir", source)


if __name__ == "__main__":
    unittest.main()
