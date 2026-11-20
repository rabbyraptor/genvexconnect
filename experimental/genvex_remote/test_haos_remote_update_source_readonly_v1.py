"""Offline tests for stopped-App source fingerprint gate, no HAOS access."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/audit_haos_remote_update_source_readonly_v1.sh"
FIXED = "/mnt/data/supervisor/apps/local/genvex_nabto_remote"
FILES = ("config.yaml", "Dockerfile", "run.sh", "runtime/app_bootstrap.py",
         "runtime/profile_provision.py")


class UpdateSourceReadOnlyTests(unittest.TestCase):
    def test_preflight_and_shell_syntax(self):
        self.assertEqual(subprocess.run(["sh", "-n", str(SCRIPT)]).returncode, 0)
        proc = subprocess.run(["sh", str(SCRIPT), "--preflight"],
                              text=True, capture_output=True, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PASS: inert preflight", proc.stdout)

    def audit(self, *, state="stopped", boot="manual", running="false", missing=None,
              source_symlink=False):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            source = home / "source"
            source.mkdir()
            (source / "runtime").mkdir()
            for rel in FILES:
                file = source / rel
                file.write_text("FAKE SOURCE CODE ONLY\\n")
            if missing:
                (source / missing).unlink()
            if source_symlink:
                original = home / "source-original"
                source.rename(original)
                source.symlink_to(original, target_is_directory=True)
            ha = home / "ha"
            ha.write_text(
                "#!/bin/sh\n"
                "cat >/dev/null\n"
                "printf '%s\\n' '  name: unlock_secret' '  value: SECRET'"
                f" 'state: {state}' 'boot: manual' 'version: 0.1.0-dev1'\n"
            )
            docker = home / "docker"
            docker.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = inspect ]; then\n"
                "  if [ \"$4\" = app_local_genvex_nabto_remote ]; then\n"
                "    if [ \"$5\" = --format ]; then echo \"$FAKE_RUNNING\"; fi\n"
                "    exit 0\n"
                "  fi\n"
                "fi\n"
                "exit 9\n"
            )
            for x in (ha, docker):
                x.chmod(0o700)
            env = os.environ.copy()
            env["PATH"] = str(home) + os.pathsep + env["PATH"]
            env["FAKE_RUNNING"] = running
            code = SCRIPT.read_text().replace(FIXED, str(source))
            proc = subprocess.run(["sh", "-s", "--", "--execute-readonly"],
                                  input=code, capture_output=True, text=True,
                                  timeout=10, env=env)
            return proc

    def test_normal_source_fingerprinting(self):
        p = self.audit()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(p.stdout.count("SOURCE: "), len(FILES))
        self.assertIn("AUDIT COMPLETE", p.stdout)
        self.assertNotIn("SECRET", p.stdout)

    def test_running_app_refused(self):
        p = self.audit(running="true")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("BLOCKED:", p.stdout)

    def test_supervisor_started_refused(self):
        p = self.audit(state="started")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("BLOCKED:", p.stdout)

    def test_automatic_boot_refused(self):
        p = self.audit(boot="auto")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("BLOCKED:", p.stdout)

    def test_missing_required_file_refused(self):
        p = self.audit(missing="runtime/profile_provision.py")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("BLOCKED:", p.stdout)

    def test_linked_root_refused(self):
        p = self.audit(source_symlink=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("BLOCKED:", p.stdout)

    def test_does_not_touch_data_or_mutate_apps(self):
        s = SCRIPT.read_text()
        self.assertNotIn("/apps/data/", s)
        for forbidden in ("options.json", "client.crt", "client-encrypted.key",
                          "ipc-token", "ha apps start", "ha apps stop",
                          "ha store reload", "ha apps update", "docker exec",
                          "chmod ", "chown ", "nabtoRpcInvoke"):
            self.assertNotIn(forbidden, s)


if __name__ == "__main__":
    unittest.main()
