"""Offline fake Supervisor CLI capability check; never invokes app updates."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/audit_haos_dev2_update_cli_capabilities_v1.sh"


class UpdateCliCapabilitiesTest(unittest.TestCase):
    def test_inert_preflight_and_syntax(self):
        self.assertEqual(subprocess.run(["sh", "-n", str(SCRIPT)]).returncode, 0)
        p = subprocess.run(["sh", str(SCRIPT), "--preflight"],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("PASS: inert preflight", p.stdout)

    def run_fake(self, *, state="stopped", latest="0.1.0-dev2",
                 update="true", help_text="Usage: ha apps update --backup",
                 fail_help=False, running=False):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            log = root / "calls"
            ha = root / "ha"
            ha.write_text(
                "#!/bin/sh\n"
                'printf "%s\\n" "$*" >> "$FAKE_CALLS"\n'
                'if [ "$1" = apps ] && [ "$2" = info ]; then\n'
                '''  printf '%s\\n' '  unlock_secret: NEVER_LOG' \
"state: $FAKE_STATE" 'boot: manual' \
'version: 0.1.0-dev1' "version_latest: $FAKE_LATEST" \
"update_available: $FAKE_UPDATE"\n'''
                "  exit 0\n"
                "fi\n"
                'if [ "$1" = apps ] && [ "$2" = update ] && [ "$3" = --help ]; then\n'
                '  [ "$FAKE_HELP_FAIL" = no ] || exit 1\n'
                '  printf "%s\\n" "$FAKE_HELP"\n'
                "  exit 0\n"
                "fi\n"
                "exit 7\n"
            )
            docker = root / "docker"
            docker.write_text(
                "#!/bin/sh\n"
                'if [ "$1" = inspect ]; then\n'
                '  if [ "$FAKE_RUNNING" = yes ]; then\n'
                '    case "$*" in *--format*) echo true;; esac\n'
                "    exit 0\n"
                "  fi\n"
                "fi\n"
                "exit 1\n"
            )
            for exe in (ha, docker):
                exe.chmod(0o700)
            env = os.environ.copy()
            env.update({
                "PATH": str(root) + os.pathsep + env["PATH"],
                "FAKE_CALLS": str(log),
                "FAKE_STATE": state,
                "FAKE_LATEST": latest,
                "FAKE_UPDATE": update,
                "FAKE_HELP": help_text,
                "FAKE_HELP_FAIL": "yes" if fail_help else "no",
                "FAKE_RUNNING": "yes" if running else "no",
            })
            proc = subprocess.run(
                ["sh", "-s", "--", "--execute-readonly"],
                input=SCRIPT.read_text(), capture_output=True,
                text=True, env=env, timeout=10,
            )
            return proc, log.read_text().splitlines() if log.exists() else []

    def test_help_backup_and_no_mutation(self):
        p, commands = self.run_fake()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("advertises --backup", p.stdout)
        self.assertNotIn("NEVER_LOG", p.stdout)
        self.assertEqual(commands, [
            "apps info local_genvex_nabto_remote", "apps update --help",
        ])

    def test_no_backup_flag_is_revealed(self):
        p, commands = self.run_fake(help_text="Usage: update <slug>")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("does not advertise --backup", p.stdout)
        self.assertEqual(len(commands), 2)

    def test_help_error_does_not_update(self):
        p, commands = self.run_fake(fail_help=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(len(commands), 2)

    def test_started_stale_or_unavailable_refused(self):
        for kwargs in (
            {"state": "started"}, {"latest": "0.1.0-dev1"},
            {"update": "false"}, {"running": True},
        ):
            with self.subTest(kwargs=kwargs):
                p, commands = self.run_fake(**kwargs)
                self.assertNotEqual(p.returncode, 0)
                self.assertNotIn("apps update --help", commands)

    def test_no_mutating_commands_in_script(self):
        text = SCRIPT.read_text()
        self.assertEqual(text.count("ha apps update --help"), 1)
        for bad in (
            "ha store reload", "ha apps start", "ha apps stop",
            "ha apps update local_", "/apps/data/", "options.json",
            "client-encrypted.key", "ipc_token", "nabtoRpcInvoke",
            "ha backups new", "curl -X POST",
        ):
            self.assertNotIn(bad, text)


if __name__ == "__main__":
    unittest.main()
