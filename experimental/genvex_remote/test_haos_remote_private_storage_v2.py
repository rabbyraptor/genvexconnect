"""Offline streamed-SSH regression for metadata-only App storage diagnosis."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/audit_haos_remote_private_storage_v2.sh"
PARENT = "/mnt/data/supervisor/apps/data"
APP = PARENT + "/local_genvex_nabto_remote"


class StorageV2AuditTests(unittest.TestCase):
    def test_preflight_and_syntax(self):
        self.assertEqual(subprocess.run(["sh", "-n", str(SCRIPT)]).returncode, 0)
        result = subprocess.run(["sh", str(SCRIPT), "--preflight"],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS: inert preflight", result.stdout)

    def run_audit(self, *, mode=0o755, state="stopped", mount_ok=True,
                  app_symlink=False):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            directory = home / "appdata"
            directory.mkdir(mode=0o700)
            app = directory / "dedicated-app"
            if app_symlink:
                elsewhere = home / "elsewhere"
                elsewhere.mkdir()
                app.symlink_to(elsewhere, target_is_directory=True)
            else:
                app.mkdir(mode=mode)
                app.chmod(mode)
            ha = home / "ha"
            ha.write_text(
                "#!/bin/sh\n"
                "cat >/dev/null\n"
                "printf '%s\\n' '  name: unlock_secret' '  value: REDACTME' "
                f"'boot: manual' 'state: {state}' 'version: 0.1.0-dev1'\n"
            )
            docker = home / "docker"
            mount = "/mnt/data/supervisor" if mount_ok else "/other"
            docker.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" != inspect ]; then exit 8; fi\n"
                "case \"$4\" in\n"
                "  app_local_genvex_nabto_remote) exit 1 ;;\n"
                f"  hassio_supervisor) printf '%s\\n' '{mount}'; exit 0 ;;\n"
                "esac\n"
                "exit 8\n"
            )
            for binary in (ha, docker):
                binary.chmod(0o700)
            source = SCRIPT.read_text().replace(APP, str(app)).replace(
                PARENT, str(directory)
            )
            env = os.environ.copy()
            env["PATH"] = str(home) + os.pathsep + env["PATH"]
            return subprocess.run(
                ["sh", "-s", "--", "--execute-readonly"],
                input=source, capture_output=True, text=True,
                timeout=10, env=env
            )

    def test_normal_supervisor_directory_mode_is_reported_not_modified(self):
        run = self.run_audit()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("app directory mode=755", run.stdout)
        self.assertIn("REVIEW:", run.stdout)
        self.assertIn("NOT READY:", run.stdout)
        self.assertIn("AUDIT COMPLETE v2", run.stdout)
        self.assertNotIn("REDACTME", run.stdout)
        self.assertNotIn("unlock_secret", run.stdout)

    def test_private_directory_mode(self):
        run = self.run_audit(mode=0o700)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("owner-only permissions", run.stdout)

    def test_running_state_blocks(self):
        run = self.run_audit(state="started")
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("BLOCKED:", run.stdout)

    def test_wrong_mount_blocks(self):
        run = self.run_audit(mount_ok=False)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("BLOCKED:", run.stdout)

    def test_symlink_blocks(self):
        run = self.run_audit(app_symlink=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("symlinked", run.stdout)

    def test_no_mutation_or_private_data_access(self):
        source = SCRIPT.read_text()
        self.assertIn("ha apps info local_genvex_nabto_remote </dev/null", source)
        for forbidden in (
            "chmod ", "chown ", "mkdir ", "docker exec", "docker start",
            "docker run", "ha apps start", "ha apps install", "nabtoRpcInvoke",
            "options.json", "client-encrypted.key", "client.crt", "ipc-token",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
