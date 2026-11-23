"""Offline checks of the single explicitly approved Supervisor catalog reload."""
from pathlib import Path
import hashlib
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/reload_haos_dev2_store_once_v1.sh"
BASE = "/mnt/data/supervisor/apps/local"
FILES = {
    "genvex_nabto_remote/config.yaml":
        "9c3099526543b19d6227cc8e56fbdc63b02c1c1635deff5a08f7afb7f0b1abb4",
    "genvex_nabto_remote/runtime/profile_provision.py":
        "f5b4580faeacedd1d2f73f1392864198b457af230d723217f49afa68949b67a6",
    ".genvex-remote-dev1-source-backup/config.yaml":
        "5c15ac644063f1a0fbcbcc3fd2050a56715922bf7f7f5640032b6f49bcdbfaac",
    ".genvex-remote-dev1-source-backup/runtime/profile_provision.py":
        "3d35505bfc12b24cc0f68e0a437c6fce047ffe2613ab13ccb10fe2959ec1fe82",
}


class OneTimeStoreReloadTests(unittest.TestCase):
    def test_shell_and_inert_preflight(self):
        self.assertEqual(subprocess.run(["sh", "-n", str(SCRIPT)]).returncode, 0)
        run = subprocess.run(["sh", str(SCRIPT), "--preflight"],
                             text=True, capture_output=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("PASS: inert preflight", run.stdout)

    def simulate(self, *, state="stopped", initial_latest="0.1.0-dev1",
                 latest_after="0.1.0-dev2", after_update="true",
                 reload_failure=False, corrupt=False, occupied=False,
                 already_offered=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / "source-local"
            base.mkdir()
            replacements = {}
            for index, (rel, original) in enumerate(FILES.items()):
                target = base / rel
                target.parent.mkdir(exist_ok=True)
                target.write_text(f"FAKE SOURCE {index}\n")
                replacements[original] = hashlib.sha256(target.read_bytes()).hexdigest()
            if corrupt:
                (base / "genvex_nabto_remote/config.yaml").write_text("CORRUPTED")
            if occupied:
                (base / ".genvex-remote-dev2-source-stage").mkdir()
            ha = root / "ha"
            log = root / "reload-calls"
            ha.write_text(
                "#!/bin/sh\n"
                'if [ "$1" = store ] && [ "$2" = reload ]; then\n'
                '  printf "reload\\n" >> "$RELOAD_LOG"\n'
                '  [ "$FAIL_RELOAD" = no ] || exit 2\n'
                '  touch "$RELOAD_FLAG"\n'
                "  exit 0\n"
                "fi\n"
                'if [ "$1" != apps ] || [ "$2" != info ]; then exit 4; fi\n'
                'if [ -e "$RELOAD_FLAG" ]; then\n'
                '  latest="$LATEST_AFTER"; update="$UPDATE_AFTER"\n'
                "else\n"
                '  latest="$LATEST_BEFORE"; update="$UPDATE_BEFORE"\n'
                "fi\n"
                '''printf '%s\\n' "state: $APP_STATE" 'boot: manual' \
'version: 0.1.0-dev1' "version_latest: $latest" \
"update_available: $update" '  unlock_secret: TOP_SECRET'\n'''
            )
            docker = root / "docker"
            docker.write_text("#!/bin/sh\nexit 1\n")
            for binary in (ha, docker):
                binary.chmod(0o700)
            env = os.environ.copy()
            env["PATH"] = str(root) + os.pathsep + env["PATH"]
            env["APP_STATE"] = state
            env["LATEST_BEFORE"] = ("0.1.0-dev2" if already_offered
                                    else initial_latest)
            env["UPDATE_BEFORE"] = "true" if already_offered else "false"
            env["LATEST_AFTER"] = latest_after
            env["UPDATE_AFTER"] = after_update
            env["RELOAD_LOG"] = str(log)
            env["RELOAD_FLAG"] = str(root / "reloaded")
            env["FAIL_RELOAD"] = "yes" if reload_failure else "no"
            code = SCRIPT.read_text().replace(BASE, str(base))
            for old, new in replacements.items():
                code = code.replace(old, new)
            run = subprocess.run(
                ["sh", "-s", "--", "--execute-approved"],
                input=code, text=True, capture_output=True, env=env, timeout=10,
            )
            return run, log.read_text().splitlines() if log.exists() else []

    def test_one_reload_and_update_offered(self):
        run, calls = self.simulate()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(calls, ["reload"])
        self.assertIn("PASS: Supervisor offers dev2 update, not installed", run.stdout)
        self.assertNotIn("TOP_SECRET", run.stdout)

    def test_does_not_reload_when_already_offered(self):
        run, calls = self.simulate(already_offered=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(calls, [])
        self.assertIn("WITHOUT RELOAD", run.stdout)

    def test_no_retry_when_reload_fails(self):
        run, calls = self.simulate(reload_failure=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(calls, ["reload"])
        self.assertIn("no retry", run.stdout)

    def test_async_catalog_not_ready_is_safe(self):
        run, calls = self.simulate(latest_after="0.1.0-dev1", after_update="false")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(calls, ["reload"])
        self.assertIn("dev2 not yet confirmed", run.stdout)

    def test_stopped_state_required(self):
        run, calls = self.simulate(state="started")
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(calls, [])

    def test_corrupt_source_blocks_reload(self):
        run, calls = self.simulate(corrupt=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(calls, [])

    def test_staging_conflict_blocks_reload(self):
        run, calls = self.simulate(occupied=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(calls, [])

    def test_no_app_update_secrets_or_write_commands(self):
        source = SCRIPT.read_text()
        self.assertEqual(source.count("ha store reload </dev/null"), 1)
        for forbidden in (
            "ha apps update", "ha apps install", "ha apps start",
            "ha apps stop", "ha store add", "docker run", "docker exec",
            "/apps/data/", "options.json", "client-encrypted.key",
            "unlock_secret", "ipc_token", "nabtoRpcInvoke",
            "\nmv ", "\nrm ", "\nchmod ",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
