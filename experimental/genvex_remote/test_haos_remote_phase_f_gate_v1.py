"""Offline regression checks for the read-only HAOS phase F gate."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/audit_haos_remote_phase_f_gate_v1.sh"


class PhaseFGateTests(unittest.TestCase):
    def test_syntax_and_inert_preflight(self):
        self.assertEqual(subprocess.run(["sh", "-n", str(SCRIPT)]).returncode, 0)
        r = subprocess.run(["sh", str(SCRIPT), "--preflight"],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0)
        self.assertIn("PASS: inert preflight", r.stdout)

    def run_gate(self, state="stopped", boot="manual", version="0.1.0-dev1"):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            (folder / "ha").write_text(
                "#!/bin/sh\n"
                "cat >/dev/null\n"
                "printf '%s\\n' 'name: Genvex Remote' '  name: unlock_secret' "
                "'  value: TOPSECRET' '  name: ipc_token' "
                f"'boot: {boot}' 'state: {state}' 'version: {version}'\n"
            )
            (folder / "docker").write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = inspect ]; then exit 1; fi\n"
                "exit 2\n"
            )
            for name in ("ha", "docker"):
                (folder / name).chmod(0o700)
            env = os.environ.copy()
            env["PATH"] = str(folder) + os.pathsep + env["PATH"]
            return subprocess.run(
                ["sh", "-s", "--", "--execute-readonly"],
                input=SCRIPT.read_bytes(), capture_output=True, env=env,
                timeout=10
            )

    def test_stopped_and_secret_safe(self):
        r = self.run_gate()
        self.assertEqual(r.returncode, 0, r.stderr.decode())
        out = r.stdout.decode()
        self.assertIn("GATE COMPLETE", out)
        self.assertIn("Supervisor App stopped", out)
        self.assertNotIn("TOPSECRET", out)
        self.assertNotIn("unlock_secret", out)

    def test_running_blocks(self):
        r = self.run_gate(state="started")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("still running", r.stdout.decode())

    def test_wrong_version_blocks(self):
        r = self.run_gate(version="0.2.0")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("version mismatch", r.stdout.decode())

    def test_wrong_boot_blocks(self):
        r = self.run_gate(boot="auto")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("boot mode", r.stdout.decode())

    def test_no_mutations(self):
        s = SCRIPT.read_text()
        self.assertIn("ha apps info local_genvex_nabto_remote </dev/null", s)
        for forbidden in ("ha apps start", "ha apps stop", "ha apps install",
                          "docker start", "docker run", "docker exec",
                          "nabtoRpcInvoke"):
            self.assertNotIn(forbidden, s)


if __name__ == "__main__":
    unittest.main()
