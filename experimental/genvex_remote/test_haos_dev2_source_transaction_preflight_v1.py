"""Synthetic-only source transaction readiness tests, never touch HAOS."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/audit_haos_dev2_source_transaction_preflight_v1.sh"
HOST_BASE = "/mnt/data/supervisor/apps/local"
BASE_FILES = {
    "config.yaml": "5c15ac644063f1a0fbcbcc3fd2050a56715922bf7f7f5640032b6f49bcdbfaac",
    "Dockerfile": "5c7edfb109ccad4b09a19ff28c3173e405bcb33eb26034174ee10de83d2f4cdd",
    "run.sh": "50c68a9defb3c47621ab6d3b901b3e645ac19f539616457f469a1cb76a91f398",
    "runtime/app_bootstrap.py": "9e8862450d6204d21136baae25ce37aa24aa591f1008842c5914911517db7db1",
    "runtime/profile_provision.py": "3d35505bfc12b24cc0f68e0a437c6fce047ffe2613ab13ccb10fe2959ec1fe82",
}


class SourceTransactionGateTest(unittest.TestCase):
    def test_preflight_and_syntax(self):
        self.assertEqual(subprocess.run(["sh", "-n", str(SCRIPT)]).returncode, 0)
        run = subprocess.run(["sh", str(SCRIPT), "--preflight"],
                             text=True, capture_output=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("inert preflight", run.stdout)

    def execute(self, *, status="stopped", boot="manual",
                drift=False, extra=False, occupied=False, linked=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / "local"
            base.mkdir()
            app = base / "genvex_nabto_remote"
            app.mkdir()
            (app / "runtime").mkdir()
            for name in BASE_FILES:
                file = app / name
                file.write_text("FAKE\n")
            if extra:
                (app / "runtime" / "secret.key").write_text("TEST ONLY")
            if linked:
                (app / "runtime" / "surprise.py").symlink_to(app / "config.yaml")
            if occupied:
                (base / ".genvex-remote-dev1-source-backup").mkdir()
            ha = root / "ha"
            ha.write_text(
                "#!/bin/sh\n"
                "cat >/dev/null\n"
                "printf '%s\\n' '  name: ipc_token' '  value: SECRET' "
                f"'state: {status}' 'boot: {boot}' 'version: 0.1.0-dev1'\n"
            )
            docker = root / "docker"
            docker.write_text("#!/bin/sh\nexit 1\n")
            checksum = root / "sha256sum"
            contents = "\n".join(
                f'  *"/{name}") echo "{sha}  $1" ;;'
                for name, sha in BASE_FILES.items()
            )
            if drift:
                contents = contents.replace(next(iter(BASE_FILES.values())), "0" * 64)
            checksum.write_text(
                "#!/bin/sh\n"
                "case \"$1\" in\n" + contents +
                "\n  *) exit 1 ;;\nesac\n"
            )
            for binary in (ha, docker, checksum):
                binary.chmod(0o700)
            code = SCRIPT.read_text().replace(HOST_BASE, str(base))
            env = os.environ.copy()
            env["PATH"] = str(root) + os.pathsep + env["PATH"]
            return subprocess.run(["sh", "-s", "--", "--execute-readonly"],
                                  input=code, text=True, capture_output=True,
                                  timeout=10, env=env)

    def test_baseline_match_passes(self):
        run = self.execute()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("GATE COMPLETE", run.stdout)
        self.assertNotIn("SECRET", run.stdout)

    def test_fails_if_source_drift(self):
        run = self.execute(drift=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("differs from recorded baseline", run.stdout)

    def test_fails_if_started_or_auto(self):
        for args in ({"status": "started"}, {"boot": "auto"}):
            with self.subTest(args=args):
                run = self.execute(**args)
                self.assertNotEqual(run.returncode, 0)
                self.assertIn("BLOCKED", run.stdout)

    def test_fails_if_source_contains_unexpected_entry(self):
        for args in ({"extra": True}, {"linked": True}):
            with self.subTest(args=args):
                run = self.execute(**args)
                self.assertNotEqual(run.returncode, 0)
                self.assertIn("unexpected or linked source", run.stdout)

    def test_fails_if_backup_path_exists(self):
        run = self.execute(occupied=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("already staged or backed up", run.stdout)

    def test_does_not_touch_app_data_or_mutate_system(self):
        source = SCRIPT.read_text()
        self.assertNotIn("/apps/data/", source)
        self.assertIn("runtime/*.py", source)
        self.assertIn("config.yaml 5c15ac644", source)
        for unsafe in ("ha apps start", "ha apps update", "ha apps stop",
                       "ha store reload", "docker exec", "mv ", "rm -rf",
                       "client-encrypted.key", "ipc-token", "options.json"):
            self.assertNotIn(unsafe, source)


if __name__ == "__main__":
    unittest.main()
