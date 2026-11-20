"""Regression for the HAOS v2 staging error: scripts/ must keep repo layout.

Entirely offline. The only scripts invoked are guarded --preflight tests.
No Docker, SDK, credentials, real Nabto session or host network access.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/run_haos_v2_offline_preflight_v2.sh"
PINNED = "189d48a641ef613023c1060f7d6cf2b2f7369b34"


class V2RepositoryLayoutRunnerTests(unittest.TestCase):
    def test_syntax_and_inert_preview(self):
        syntax = subprocess.run(
            ["sh", "-n", str(RUNNER)], capture_output=True, text=True,
            timeout=10,
        )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        result = subprocess.run(
            ["sh", str(RUNNER), "--preflight"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OFFLINE PREFLIGHT v2 / REPO LAYOUT", result.stdout)
        self.assertIn("no container/network operations", result.stdout)
        self.assertIn(PINNED, result.stdout)

    def test_guarded_options_and_exact_staging(self):
        for args in ([], ["--execute-live"], ["--preflight", "--execute-offline"]):
            with self.subTest(args=args):
                result = subprocess.run(
                    ["sh", str(RUNNER), *args],
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 2)
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn('PROJECT_ROOT=$(dirname "$(dirname "$SRC")")', source)
        self.assertIn('experimental/genvex_remote experimental/home_assistant scripts', source)
        self.assertIn('tar -xf - -C "$STAGE/project"', source)
        self.assertIn('cd "$1/project/experimental/genvex_remote"', source)
        self.assertIn('cd "$1/project/experimental/home_assistant/tests"', source)
        self.assertIn("test_v2_snapshot_bridge.py", source)
        self.assertIn(PINNED, source)
        self.assertNotIn("nabtoRpcInvoke", source)
        self.assertNotIn("docker cp", source)
        self.assertNotIn("unlock_secret", source)

    def test_repo_relative_script_tests_in_recreated_layout(self):
        """Missing scripts/ must fail here, independently of full CI suite."""
        with tempfile.TemporaryDirectory(prefix="genvex-v2-layout-") as temp:
            root = Path(temp) / "project"
            backend = root / "experimental/genvex_remote"
            backend.parent.mkdir(parents=True)
            shutil.copytree(
                ROOT / "experimental/genvex_remote", backend,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            shutil.copytree(ROOT / "scripts", root / "scripts")
            shutil.copytree(
                ROOT / "experimental/home_assistant",
                root / "experimental/home_assistant",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            result = subprocess.run(
                [
                    sys.executable, "-m", "unittest",
                    "test_deck_runner_preflight",
                    "test_seven_snapshot_v2_probe",
                    "test_single_candidate_cli",
                    "test_twelve_candidate_batch",
                ],
                cwd=backend, capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stderr[-3500:])
            self.assertIn("OK", result.stderr)


if __name__ == "__main__":
    unittest.main()
