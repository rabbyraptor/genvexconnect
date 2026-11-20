"""Offline tests for source-only read-only HAOS private-storage gate."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/audit_haos_remote_private_storage_v1.sh"
HOST_PATH = "/mnt/data/supervisor/apps/data/local_genvex_nabto_remote"


class PrivateStorageGateTests(unittest.TestCase):
    def test_syntax_and_preflight(self):
        self.assertEqual(subprocess.run(["sh", "-n", str(SCRIPT)]).returncode, 0)
        run = subprocess.run(["sh", str(SCRIPT), "--preflight"],
                             capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("PASS: inert preflight", run.stdout)

    def run_gate(self, *, state="stopped", boot="manual",
                 version="0.1.0-dev1", mode=0o700, supervisor_mount=True):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = root / "private-app"
            store.mkdir(mode=mode)
            store.chmod(mode)
            ha = root / "ha"
            ha.write_text(
                "#!/bin/sh\n"
                "cat >/dev/null\n"
                "printf '%s\\n' '  name: unlock_secret' '  value: REDACTME' "
                f"'state: {state}' 'boot: {boot}' 'version: {version}'\n"
            )
            docker = root / "docker"
            mount = "/mnt/data/supervisor" if supervisor_mount else "/wrong-path"
            docker.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" != inspect ]; then exit 8; fi\n"
                "if [ \"$4\" = app_local_genvex_nabto_remote ]; then exit 1; fi\n"
                f"if [ \"$4\" = hassio_supervisor ]; then printf '%s\\n' '{mount}'; exit 0; fi\n"
                "exit 8\n"
            )
            for x in (ha, docker):
                x.chmod(0o700)
            code = SCRIPT.read_text().replace(HOST_PATH, str(store))
            env = os.environ.copy()
            env["PATH"] = str(root) + os.pathsep + env["PATH"]
            return subprocess.run(
                ["sh", "-s", "--", "--execute-readonly"],
                input=code, text=True, capture_output=True, timeout=10, env=env
            )

    def test_expected_stopped_private_storage(self):
        run = self.run_gate()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("AUDIT COMPLETE", run.stdout)
        self.assertIn("permissions are 0700", run.stdout)
        self.assertNotIn("REDACTME", run.stdout)
        self.assertNotIn("unlock_secret", run.stdout)

    def test_running_refused(self):
        run = self.run_gate(state="started")
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("BLOCKED", run.stdout)

    def test_mount_mismatch_refused(self):
        run = self.run_gate(supervisor_mount=False)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("mount differs", run.stdout)

    def test_group_readable_refused(self):
        run = self.run_gate(mode=0o750)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("permissions are not 0700", run.stdout)

    def test_no_secret_access_or_mutations(self):
        source = SCRIPT.read_text()
        self.assertIn("ha apps info local_genvex_nabto_remote </dev/null", source)
        self.assertIn("stat -c '%a' \"$APP_DIR\"", source)
        for forbidden in ("cat \"$APP_DIR", "find \"$APP_DIR", "ls \"$APP_DIR",
                          "ha apps start", "ha apps stop", "ha apps install",
                          "docker start", "docker run", "docker exec",
                          "nabtoRpcInvoke", "/profile/client"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
