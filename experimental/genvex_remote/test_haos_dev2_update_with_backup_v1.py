"""Offline fake CLI contracts: no implicit update, backup required, stopped App."""
from pathlib import Path
import hashlib
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/update_haos_genvex_remote_dev2_with_backup_v1.sh"
BASE = "/mnt/data/supervisor/apps/local"
HASHES = {
    "genvex_nabto_remote/config.yaml":
        "9c3099526543b19d6227cc8e56fbdc63b02c1c1635deff5a08f7afb7f0b1abb4",
    "genvex_nabto_remote/runtime/profile_provision.py":
        "f5b4580faeacedd1d2f73f1392864198b457af230d723217f49afa68949b67a6",
    ".genvex-remote-dev1-source-backup/config.yaml":
        "5c15ac644063f1a0fbcbcc3fd2050a56715922bf7f7f5640032b6f49bcdbfaac",
    ".genvex-remote-dev1-source-backup/runtime/profile_provision.py":
        "3d35505bfc12b24cc0f68e0a437c6fce047ffe2613ab13ccb10fe2959ec1fe82",
}


class BackupUpdateContractTest(unittest.TestCase):
    def test_inert_preflight_and_shell_syntax(self):
        self.assertEqual(subprocess.run(["sh", "-n", str(SCRIPT)]).returncode, 0)
        result = subprocess.run(["sh", str(SCRIPT), "--preflight"],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertIn("inert preflight", result.stdout)

    def run_fake(self, *, state="stopped", latest="0.1.0-dev2",
                 update="true", help_backup=True, fail_update=False,
                 headroom=900000, changed=False, running=False):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_base = root / "source"
            source_base.mkdir()
            replacements = {}
            for i, (relative, expected) in enumerate(HASHES.items()):
                file = source_base / relative
                file.parent.mkdir(exist_ok=True)
                file.write_text(f"FAKE {i}\n")
                replacements[expected] = hashlib.sha256(file.read_bytes()).hexdigest()
            if changed:
                (source_base / "genvex_nabto_remote/config.yaml").write_text("DRIFT")
            ha = root / "ha"
            calls = root / "ha-calls"
            ha.write_text(
                "#!/bin/sh\n"
                'printf "CALL:%s\\n" "$*" >> "$CALL_LOG"\n'
                'if [ "$1" = apps ] && [ "$2" = info ]; then\n'
                '  if [ -e "$UPDATED_FLAG" ]; then\n'
                "    v=0.1.0-dev2; update=false\n"
                "  else\n"
                '    v=0.1.0-dev1; update="$BEFORE_UPDATE"\n'
                "  fi\n"
                '  printf "%s\\n" "state: $BEFORE_STATE" "boot: manual" '
                '"version: $v" "version_latest: $LATEST" '
                '"update_available: $update" "  unlock_secret: NOT_PRINTED"\n'
                "  exit 0\n"
                "fi\n"
                'if [ "$1" = apps ] && [ "$2" = update ] && [ "$3" = --help ]; then\n'
                '  if [ "$HAS_BACKUP" = yes ]; then echo "Usage --backup"; '
                'else echo "Usage update"; fi\n'
                "  exit 0\n"
                "fi\n"
                'if [ "$1" = apps ] && [ "$2" = update ] && '
                '[ "$3" = local_genvex_nabto_remote ] && [ "$4" = --backup ]; then\n'
                '  [ "$FAIL_UPDATE" = no ] || exit 3\n'
                '  touch "$UPDATED_FLAG"\n'
                "  exit 0\n"
                "fi\n"
                "exit 8\n"
            )
            docker = root / "docker"
            docker.write_text(
                "#!/bin/sh\n"
                'if [ "$1" = inspect ] && [ "$RUNNING" = yes ]; then\n'
                '  case "$*" in *--format*) echo true ;; esac\n'
                "  exit 0\n"
                "fi\n"
                "exit 1\n"
            )
            df = root / "df"
            df.write_text(
                "#!/bin/sh\n"
                'printf "%s\\n" "Filesystem 1024-blocks Used Available Capacity Mounted" '
                f'"tmpfs 1000000 1000 {headroom} 10% /fake"\n'
            )
            for cmd in (ha, docker, df):
                cmd.chmod(0o700)
            env = os.environ.copy()
            env.update({
                "PATH": str(root) + os.pathsep + env["PATH"],
                "CALL_LOG": str(calls),
                "UPDATED_FLAG": str(root / "updated"),
                "BEFORE_STATE": state,
                "BEFORE_UPDATE": update,
                "LATEST": latest,
                "HAS_BACKUP": "yes" if help_backup else "no",
                "FAIL_UPDATE": "yes" if fail_update else "no",
                "RUNNING": "yes" if running else "no",
            })
            code = SCRIPT.read_text().replace(BASE, str(source_base))
            for original, fake in replacements.items():
                code = code.replace(original, fake)
            result = subprocess.run(
                ["sh", "-s", "--", "--execute-approved"],
                input=code, text=True, capture_output=True, env=env, timeout=10,
            )
            return result, calls.read_text().split("CALL:")[1:] if calls.exists() else []

    def test_only_one_backup_enabled_update(self):
        result, calls = self.run_fake()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(sum("apps update local_genvex_nabto_remote --backup" in c
                             for c in calls), 1)
        self.assertIn("installed App dev2, stopped/manual", result.stdout)
        self.assertNotIn("NOT_PRINTED", result.stdout)

    def test_refuses_drift_running_or_missing_update(self):
        for args in (
            {"changed": True}, {"running": True}, {"state": "started"},
            {"update": "false"}, {"latest": "0.1.0-dev1"},
            {"help_backup": False}, {"headroom": 20000},
        ):
            with self.subTest(args=args):
                result, calls = self.run_fake(**args)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("apps update local_genvex_nabto_remote --backup",
                                 "".join(calls))

    def test_failure_never_retries(self):
        result, calls = self.run_fake(fail_update=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sum("apps update local_genvex_nabto_remote --backup" in c
                             for c in calls), 1)
        self.assertIn("do not retry", result.stdout)

    def test_script_only_updates_target_with_backup(self):
        s = SCRIPT.read_text()
        self.assertEqual(s.count("ha apps update local_genvex_nabto_remote --backup"), 1)
        for forbidden in (
            "ha apps install", "ha apps start", "ha apps stop",
            "ha store reload", "ha backups restore", "docker run",
            "docker exec", "/apps/data/", "options.json",
            "client-encrypted.key", "nabtoRpcInvoke",
        ):
            self.assertNotIn(forbidden, s)


if __name__ == "__main__":
    unittest.main()
