"""Offline runner safety checks: no Docker, downloads or SDK calls executed."""
from __future__ import annotations

from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/archive/run_haos_v2_offline_preflight_v1.sh"
PINNED = "640125954c0683e13372f3317e5cb9bd0a4e39ac"


class OfflineRunnerSafetyTests(unittest.TestCase):
    def test_shell_syntax_and_preview_without_network(self):
        syntax = subprocess.run(
            ["sh", "-n", str(RUNNER)], capture_output=True, text=True,
            timeout=10,
        )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        result = subprocess.run(
            ["sh", str(RUNNER), "--preflight"], capture_output=True,
            text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS: offline preview only", result.stdout)
        self.assertIn(PINNED, result.stdout)

    def test_unapproved_modes_are_rejected(self):
        for arguments in ([], ["--execute-live"], ["--preflight", "--execute-offline"]):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    ["sh", str(RUNNER), *arguments], capture_output=True,
                    text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 2)

    def test_test_revision_and_no_live_credential_operations(self):
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn(PINNED, source)
        self.assertIn("codeload.github.com", source)
        self.assertIn("test_v2_snapshot_bridge.py", source)
        self.assertIn("test_v2_polling_state.py", source)
        self.assertIn("python3 -m unittest discover", source)
        self.assertNotIn("nabtoRpcInvoke", source)
        self.assertNotIn("unlock_secret", source)
        self.assertNotIn("profile_dir", source)
        self.assertNotIn("docker cp", source)


if __name__ == "__main__":
    unittest.main()
