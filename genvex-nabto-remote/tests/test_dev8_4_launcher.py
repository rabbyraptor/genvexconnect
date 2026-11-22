"""DEV8.4.5 pinned operator command contract; no real SSH or installation."""
from __future__ import annotations

from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/run_dev8_combined_from_deck.sh"


class Dev8RunnerTests(unittest.TestCase):
    def test_syntax_and_pinned_argument_gate(self):
        syntax = subprocess.run(
            ["bash", "-n", str(RUNNER)], capture_output=True, text=True,
        )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        bad = subprocess.run(
            ["bash", str(RUNNER), "--apply", "not-a-full-commit"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(bad.returncode, 2)
        self.assertIn("pinned-source-commit", bad.stderr)

    def test_single_archive_one_host_installer_and_preflight_gate(self):
        source = RUNNER.read_text()
        self.assertIn("package_dev8_combined.py", source)
        self.assertIn("install_dev8_combined.py", source)
        self.assertIn("genvex-remote-dev8-combined.tar.gz", source)
        self.assertEqual(source.count("cat >"), 2)  # archive + installer
        self.assertIn('if [[ "$MODE" == "--preflight" ]]; then', source)
        self.assertIn("--preflight '$REMOTE/release.tar.gz' '$sha'", source)
        self.assertIn("--apply '$REMOTE/release.tar.gz' '$sha'", source)
        self.assertIn("sha256sum -c --status DEV8_COMBINED_SHA256SUMS", source)
        self.assertIn("https://codeload.github.com/rabbyraptor/genvexconnect/tar.gz/$COMMIT", source)
        self.assertIn("BatchMode=yes", source)
        self.assertIn("StrictHostKeyChecking=yes", source)
        self.assertNotIn("StrictHostKeyChecking=no", source)
        self.assertIn("UserKnownHostsFile=$pinned", source)
        self.assertIn("STEAM_DECK_EXIT_CODE: $RC", source)
        self.assertIn(r"printf '\033[3J\033[2J\033[H'", source)

    def test_no_anonymous_or_unreviewed_host_mcp_execution(self):
        source = RUNNER.read_text()
        self.assertNotIn("curl | bash", source)
        self.assertNotIn("docker exec", source)
        self.assertNotIn("docker run", source)
        self.assertNotIn("client-encrypted.key", source)
        self.assertNotIn("GENVEX_UNLOCK_SECRET", source)


if __name__ == "__main__":
    unittest.main()
