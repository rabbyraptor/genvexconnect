"""Offline static guards for operator-authorized seven-address QEMU runner."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/run_haos_qemu_seven_v2_from_deck_v1.sh"


class SevenQemuRunnerTests(unittest.TestCase):
    def test_bash_syntax_and_inert_default(self):
        syntax = subprocess.run(["bash", "-n", str(RUNNER)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        preview = subprocess.run(["bash", str(RUNNER)],
                                 capture_output=True, text=True, timeout=10)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn("PASS: inert preview", preview.stdout)
        self.assertIn("20,21,22,23,26,18,19", preview.stdout)

    def test_explicit_live_opt_in_and_no_persistent_changes(self):
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn('--execute-live', source)
        self.assertIn('MODE="${1:---preflight}"', source)
        self.assertIn('if [[ "$MODE" == "--preflight" ]]; then', source)
        self.assertIn("BatchMode=yes", source)
        self.assertIn("probe_remote_snapshot_v2.py", source)
        self.assertIn("client-encrypted.key", source)
        self.assertIn('trap cleanup EXIT', source)
        self.assertIn('timeout -s TERM -k 5 90', source)
        self.assertIn('docker exec -i -e GENVEX_NABTO_PROFILE=', source)
        self.assertIn('python3 -c', source)
        self.assertNotIn('docker cp', source)
        self.assertNotIn('docker restart', source)
        self.assertNotIn('nabtoRpcInvoke', source)
        self.assertNotIn('docker commit', source)
        self.assertNotIn('docker build', source)

    def test_unknown_flags_do_not_access_ssh_or_credentials(self):
        for args in (["--execute-offline"], ["--execute-live", "--preflight"]):
            with self.subTest(args=args):
                result = subprocess.run(
                    ["bash", str(RUNNER), *args],
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
