"""Offline regressions for the Bash Steam Deck stdin-passphrase wrapper.

The test invokes --preflight ONLY. No account, device ID, SDK or key is used.
"""
import os
from pathlib import Path
import subprocess
import unittest


RUNNER = Path(__file__).resolve().parents[2] / "scripts" / "run_optima270_one_read_from_deck.sh"


class DeckRunnerTests(unittest.TestCase):
    def test_runner_bash_syntax(self):
        result = subprocess.run(
            ["bash", "-n", str(RUNNER)],
            check=False, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_default_preflight_requires_no_secrets_and_no_live_call(self):
        env = dict(os.environ)
        env.pop("GENVEX_NABTO_IDENTITY", None)
        env.pop("GENVEX_NABTO_HOST", None)
        result = subprocess.run(
            ["bash", str(RUNNER), "--preflight"],
            check=False, capture_output=True, text=True,
            env=env, input="", timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OFFLINE preview", result.stdout)
        self.assertIn("PASS: preview complete; no Nabto session was opened", result.stdout)
        self.assertNotIn("SDK startup", result.stdout)

    def test_live_runner_requires_known_host_comparison_before_passphrase(self):
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn('KNOWN_HOST', source)
        self.assertIn('if [[ "$KNOWN_HOST" != "${DEVICE_ID}.remote.lscontrol.dk" ]]', source)
        self.assertIn("no RPC will be sent", source)
        self.assertLess(
            source.index('if [[ "$KNOWN_HOST" !='),
            source.index('IFS= read -r -s -p "Nøgleadgangskode'),
        )
        self.assertLess(
            source.index('if [[ "$KNOWN_HOST" !='),
            source.index('python3 -u "$PROBE"'),
        )

    def test_unknown_option_cannot_enter_live_code(self):
        result = subprocess.run(
            ["bash", str(RUNNER), "--live-please"],
            check=False, capture_output=True, text=True, input="", timeout=10,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Usage:", result.stderr)


if __name__ == "__main__":
    unittest.main()
