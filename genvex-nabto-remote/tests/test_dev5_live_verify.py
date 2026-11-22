"""Offline contract tests for DEV5 read-only verifier (no network/HAOS)."""
from __future__ import annotations

import ast
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/run_dev5_live_verify_from_deck.sh"


class Dev5LiveVerifyContractTests(unittest.TestCase):
    def test_shell_and_both_python_payloads_parse(self):
        syntax = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True)
        self.assertEqual(syntax.returncode, 0, syntax.stderr.decode())
        source = SCRIPT.read_text()
        blocks = re.findall(
            r"^.*? <<'(?:HOST_PY|APP_PY)'\n(.*?)^(?:HOST_PY|APP_PY)$",
            source, flags=re.M | re.S,
        )
        self.assertEqual(len(blocks), 2)
        for block in blocks:
            ast.parse(block)

    def test_readonly_separate_ssh_and_mandatory_markers(self):
        source = SCRIPT.read_text()
        self.assertEqual(source.count("ssh -T -p 22222"), 3)
        self.assertNotIn("'sh -s'", source)
        for fragment in (
            "SUPERVISOR_DEV5_RUNNING: PASS",
            "DEV5_DIAGNOSTIC_IMAGE_PARITY: PASS",
            "IPC_V1_VALUES:",
            "PERSISTENT_WORKER_COUNT:",
            "HA_REGISTRY: PASS",
            "DEV5_IPC_RESULT: PASS",
            "DEV5_RUNTIME_VERIFY: PASS",
            "INCOMPLETE_LIVE_GATE",
            "STEAM_DECK_EXIT_CODE:",
        ):
            self.assertIn(fragment, source)
        for banned in (
            "ha apps start", "ha apps stop", "ha apps restart",
            "ha apps update", "docker restart", "docker cp",
        ):
            self.assertNotIn(banned, source)

    def test_early_remote_eof_cannot_report_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            fake = folder / "ssh"
            fake.write_text(
                "#!/bin/sh\n"
                "cat >/dev/null\n"
                "echo 'SUPERVISOR_DEV5_RUNNING: PASS'\n"
                "exit 0\n"
            )
            fake.chmod(0o755)
            env = dict(os.environ)
            env["PATH"] = temp + os.pathsep + env.get("PATH", "")
            result = subprocess.run(
                ["bash", str(SCRIPT)],
                capture_output=True, text=True, env=env, timeout=12,
            )
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            self.assertIn("BLOCKED: INCOMPLETE_LIVE_GATE", result.stdout)
            self.assertIn("STEAM_DECK_EXIT_CODE: 3", result.stdout)
            self.assertNotIn("DEV5_RUNTIME_VERIFY: PASS\n===== COMPLETE =====\nSTEAM_DECK_EXIT_CODE: 0", result.stdout)


if __name__ == "__main__":
    unittest.main()
