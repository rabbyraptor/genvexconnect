"""Regress the HAOS v4 literal-backslash-n staging command defect.

No Docker, network, SDK, credentials, or live Genvex operations.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/run_haos_v2_runtime_offline_v5.sh"
PIN = "a0e32de6673eb08d792262ff81a0a00e3a03a097"


class V5RunnerSafetyTests(unittest.TestCase):
    def test_inert_preview_and_shell_syntax(self):
        syntax = subprocess.run(
            ["sh", "-n", str(RUNNER)], text=True,
            capture_output=True, timeout=10,
        )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        result = subprocess.run(
            ["sh", str(RUNNER), "--preflight"], text=True,
            capture_output=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PREFLIGHT v5", result.stdout)
        self.assertIn(PIN, result.stdout)
        self.assertIn("no container/network operations", result.stdout)

    def test_every_docker_file_check_is_a_separate_shell_command(self):
        source = RUNNER.read_text(encoding="utf-8")
        self.assertNotIn(r"\ndocker exec", source)
        self.assertNotIn(r"\ntest ", source)
        checks = [
            line for line in source.splitlines()
            if line.startswith('docker exec "$APP" test -f ')
        ]
        self.assertEqual(len(checks), 4, "Every stage check must be on its own line")
        self.assertTrue(any("sdk_snapshot_adapter_v2.py" in line for line in checks))
        self.assertTrue(any("test_snapshot_v2_draft.py" in line for line in checks))
        self.assertTrue(all(line.count('docker exec') == 1 for line in checks))
        self.assertTrue(all(line.endswith('"') for line in checks))

    def test_offline_only_and_complete_layout(self):
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn(PIN, source)
        self.assertIn(
            "experimental/genvex_remote experimental/home_assistant scripts",
            source,
        )
        self.assertIn("test_runtime_v2_draft.py", source)
        self.assertIn("test_sdk_snapshot_adapter_v2.py", source)
        self.assertIn("probe_remote_snapshot_v2.py", source)
        self.assertIn("python3 -m unittest discover", source)
        self.assertNotIn("docker cp", source)
        self.assertNotIn("nabtoRpcInvoke", source)
        self.assertNotIn("unlock_secret", source)
        for args in ([], ["--execute-live"], ["--preflight", "--execute-offline"]):
            with self.subTest(args=args):
                result = subprocess.run(
                    ["sh", str(RUNNER), *args],
                    text=True, capture_output=True, timeout=10,
                )
                self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
