"""Offline regression: distinguish installed/stopped App from absent Docker container."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/archive/audit_haos_v2_ipc_supervisor_state_v1.sh"


class SupervisorStateAuditTests(unittest.TestCase):
    def test_syntax_preflight_and_no_mutations(self):
        self.assertEqual(subprocess.run(["sh", "-n", str(SCRIPT)]).returncode, 0)
        result = subprocess.run(["sh", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS: inert preflight", result.stdout)
        text = SCRIPT.read_text()
        for forbidden in ("docker run", "docker start", "docker network create",
                          "docker cp", "ha apps start", "ha apps install",
                          "cat /data/", "nabtoRpcInvoke"):
            self.assertNotIn(forbidden, text)
        self.assertIn("ha apps info local_genvex_nabto_remote --raw", text)
        self.assertIn("json.load(sys.stdin)", text)

    def test_installed_and_stopped_with_no_container_is_not_misclassified(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / "ha").write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' '{\"data\":{\"installed\":true,"
                "\"state\":\"stopped\",\"version\":\"0.1.0-dev1\","
                "\"options\":{\"unlock_secret\":\"TOPSECRET\"}}}'\n",
                encoding="utf-8",
            )
            (folder / "docker").write_text(
                "#!/bin/sh\n[ \"$1\" = inspect ] || exit 50\nexit 1\n",
                encoding="utf-8",
            )
            for name in ("ha", "docker"):
                (folder / name).chmod(0o700)
            env = os.environ.copy()
            env["PATH"] = str(folder) + os.pathsep + env.get("PATH", "")
            r = subprocess.run(["sh", str(SCRIPT), "--execute-readonly"],
                               env=env, text=True, capture_output=True, timeout=10)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("Supervisor installed: yes", r.stdout)
            self.assertIn("Supervisor state: stopped", r.stdout)
            self.assertIn("Docker dedicated App container: absent", r.stdout)
            self.assertNotIn("TOPSECRET", r.stdout + r.stderr)
            self.assertNotIn("unlock_secret", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
