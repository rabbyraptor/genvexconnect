"""Offline fake-CLI tests of non-mutating Supervisor dev2 readiness gate."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/audit_haos_dev2_supervisor_update_readiness_v1.sh"
BASE = "/mnt/data/supervisor/apps/local"


class SupervisorUpdateReadinessTests(unittest.TestCase):
    def test_preflight_and_shell(self):
        self.assertEqual(subprocess.run(["sh", "-n", str(SCRIPT)]).returncode, 0)
        result = subprocess.run(["sh", str(SCRIPT), "--preflight"],
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertIn("inert preflight", result.stdout)

    def run_fake(self, *, stopped=True, latest="0.1.0-dev1", update="false",
                 headroom=800000, corrupt=False):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            local = root / "local"
            local.mkdir()
            sources = {
                "genvex_nabto_remote/config.yaml":
                    "9c3099526543b19d6227cc8e56fbdc63b02c1c1635deff5a08f7afb7f0b1abb4",
                "genvex_nabto_remote/runtime/profile_provision.py":
                    "f5b4580faeacedd1d2f73f1392864198b457af230d723217f49afa68949b67a6",
                ".genvex-remote-dev1-source-backup/config.yaml":
                    "5c15ac644063f1a0fbcbcc3fd2050a56715922bf7f7f5640032b6f49bcdbfaac",
                ".genvex-remote-dev1-source-backup/runtime/profile_provision.py":
                    "3d35505bfc12b24cc0f68e0a437c6fce047ffe2613ab13ccb10fe2959ec1fe82",
            }
            for name in sources:
                path = local / name
                path.parent.mkdir(exist_ok=True)
                path.write_text("FAKE SOURCE")
            ha = root / "ha"
            ha.write_text(
                "#!/bin/sh\n"
                "cat >/dev/null\n"
                "printf '%s\\n' '  unlock_secret: PRIVATE' "
                f"'state: {'stopped' if stopped else 'started'}' 'boot: manual' "
                f"'version: 0.1.0-dev1' 'version_latest: {latest}' "
                f"'update_available: {update}'\n"
            )
            docker = root / "docker"
            docker.write_text("#!/bin/sh\nexit 1\n")
            sha = root / "sha256sum"
            cases = "\n".join(
                f'  *"{name}") echo "{("0"*64) if corrupt and "backup" in name else digest}  $1" ;;'
                for name, digest in sources.items()
            )
            sha.write_text(
                "#!/bin/sh\n"
                "case \"$1\" in\n" + cases + "\n  *) exit 1 ;;\nesac\n"
            )
            df = root / "df"
            df.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' 'Filesystem 1024-blocks Used Available Capacity Mounted' "
                f"'tmpfs 1234567 500 {headroom} 5% /fake'\n"
            )
            for exe in (ha, docker, sha, df):
                exe.chmod(0o700)
            env = os.environ.copy()
            env["PATH"] = str(root) + os.pathsep + env["PATH"]
            code = SCRIPT.read_text().replace(BASE, str(local))
            return subprocess.run(
                ["sh", "-s", "--", "--execute-readonly"], input=code,
                capture_output=True, text=True, env=env, timeout=10,
            )

    def test_no_reload_needed_flag(self):
        p = self.run_fake(latest="0.1.0-dev2", update="true")
        self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
        self.assertIn("Supervisor already offers dev2", p.stdout)
        self.assertNotIn("PRIVATE", p.stdout)

    def test_catalog_not_refreshed_is_not_ready(self):
        p = self.run_fake()
        self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
        self.assertIn("NOT READY", p.stdout)

    def test_app_running_refused(self):
        p = self.run_fake(stopped=False)
        self.assertNotEqual(p.returncode, 0)

    def test_corrupted_backup_refused(self):
        p = self.run_fake(corrupt=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("source differs", p.stdout)

    def test_low_disk_refused(self):
        p = self.run_fake(headroom=10000)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("less than 512 MiB", p.stdout)

    def test_surprise_version_refused(self):
        p = self.run_fake(latest="0.2.0")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("unexpected catalog version", p.stdout)

    def test_never_mutates_or_reads_app_data(self):
        s = SCRIPT.read_text()
        self.assertNotIn("/apps/data", s)
        for forbidden in (
            "ha store reload", "ha apps update", "ha apps start",
            "docker exec", "docker run", "options.json",
            "client-encrypted.key", "chmod ", "chown ", "nabtoRpcInvoke",
        ):
            self.assertNotIn(forbidden, s)


if __name__ == "__main__":
    unittest.main()
