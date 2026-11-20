"""Guard the corrected v4 runtime runner: pinned code, offline-only, full layout."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/run_haos_v2_runtime_offline_v4.sh"
PINNED = "a0e32de6673eb08d792262ff81a0a00e3a03a097"


class RuntimeV4RunnerTests(unittest.TestCase):
    def test_shell_and_preview_safe(self):
        syntax = subprocess.run(
            ["sh", "-n", str(RUNNER)], capture_output=True,
            text=True, timeout=10,
        )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        preview = subprocess.run(
            ["sh", str(RUNNER), "--preflight"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn("V2 RUNTIME OFFLINE PREFLIGHT v4", preview.stdout)
        self.assertIn(PINNED, preview.stdout)
        self.assertIn("no container/network operations", preview.stdout)

    def test_explicit_offline_and_staged_sdk_v2_files(self):
        content = RUNNER.read_text(encoding="utf-8")
        self.assertIn("experimental/genvex_remote experimental/home_assistant scripts", content)
        self.assertIn("test_runtime_v2_draft.py", content)
        self.assertIn("test_sdk_snapshot_adapter_v2.py", content)
        self.assertIn("probe_remote_snapshot_v2.py", content)
        self.assertIn("python3 -m unittest discover", content)
        self.assertNotIn("docker cp", content)
        self.assertNotIn("unlock_secret", content)
        self.assertNotIn("nabtoRpcInvoke", content)
        for args in ([], ["--execute-live"], ["--execute-offline", "--preflight"]):
            with self.subTest(args=args):
                result = subprocess.run(
                    ["sh", str(RUNNER), *args],
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
