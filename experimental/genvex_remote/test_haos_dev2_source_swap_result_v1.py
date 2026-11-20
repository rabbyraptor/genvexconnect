"""Synthetic-only regression for read-only source swap verification."""
from pathlib import Path
import hashlib
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/audit_haos_dev2_source_swap_result_v1.sh"
HOST_BASE = "/mnt/data/supervisor/apps/local"
FILENAMES = ("config.yaml", "Dockerfile", "run.sh",
             "runtime/app_bootstrap.py", "runtime/profile_provision.py")


class SourceSwapResultTests(unittest.TestCase):
    def test_syntax_and_preflight(self):
        self.assertEqual(subprocess.run(["sh", "-n", str(SCRIPT)]).returncode, 0)
        run = subprocess.run(["sh", str(SCRIPT), "--preflight"],
                             capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("inert preflight", run.stdout)

    def simulate(self, *, state="stopped", change=None, stage=False,
                 missing_backup=False, unexpected=False, linked=False):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            base = home / "local"
            base.mkdir()
            candidates = [
                base / ".genvex-remote-dev1-source-backup",
                base / "genvex_nabto_remote",
            ]
            hashes = {}
            for index, tree in enumerate(candidates):
                tree.mkdir()
                (tree / "runtime").mkdir()
                for rel in FILENAMES:
                    file = tree / rel
                    file.write_text(f"FAKE tree{index} {rel}\\n")
                    hashes[(index, rel)] = hashlib.sha256(file.read_bytes()).hexdigest()
            if change:
                (candidates[1] / change).write_text("MODIFIED")
            if stage:
                (base / ".genvex-remote-dev2-source-stage").mkdir()
            if missing_backup:
                (candidates[0] / "config.yaml").unlink()
            if unexpected:
                (candidates[1] / "unexpected.bin").write_bytes(b"FAKE")
            if linked:
                (candidates[1] / "runtime" / "unexpected.py").symlink_to(
                    candidates[1] / "config.yaml"
                )
            ha = home / "ha"
            ha.write_text(
                "#!/bin/sh\n"
                "cat >/dev/null\n"
                "printf '%s\\n' '  name: unlock_secret' '  value: NEVER_PRINT' "
                f"'state: {state}' 'boot: manual' 'version: 0.1.0-dev1'\n"
            )
            docker = home / "docker"
            docker.write_text("#!/bin/sh\nexit 1\n")
            for exe in (ha, docker):
                exe.chmod(0o700)
            code = SCRIPT.read_text().replace(HOST_BASE, str(base))
            for line in SCRIPT.read_text().splitlines():
                if line.startswith("config.yaml ") or any(
                    line.startswith(f + " ") for f in FILENAMES
                ):
                    fields = line.split()
                    original = f"{fields[0]} {hashes[(0, fields[0])]} {hashes[(1, fields[0])]}"
                    code = code.replace(line, original)
            env = os.environ.copy()
            env["PATH"] = str(home) + os.pathsep + env["PATH"]
            return subprocess.run(
                ["sh", "-s", "--", "--execute-readonly"],
                input=code, capture_output=True, text=True, timeout=10, env=env,
            )

    def test_verified_source_and_backup(self):
        run = self.simulate()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("SOURCE SWAP RESULT VERIFIED", run.stdout)
        self.assertNotIn("NEVER_PRINT", run.stdout)

    def test_mutated_dev2_refused(self):
        run = self.simulate(change="runtime/profile_provision.py")
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("fingerprint mismatch", run.stdout)

    def test_running_app_refused(self):
        run = self.simulate(state="started")
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("BLOCKED", run.stdout)

    def test_occupied_stage_refused(self):
        run = self.simulate(stage=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("temporary source stage", run.stdout)

    def test_missing_backup_file_refused(self):
        run = self.simulate(missing_backup=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("required source file missing", run.stdout)

    def test_unexpected_or_linked_source_refused(self):
        for kwargs in ({"unexpected": True}, {"linked": True}):
            with self.subTest(kwargs=kwargs):
                run = self.simulate(**kwargs)
                self.assertNotEqual(run.returncode, 0)
                self.assertIn("unexpected or linked", run.stdout)

    def test_no_mutation_and_no_private_data_read(self):
        code = SCRIPT.read_text()
        self.assertNotIn("/apps/data/", code)
        self.assertIn("0.1.0-dev1", code)
        self.assertIn("f5b4580faeacedd1d2f73f1392864198b457af230d723217f49afa68949b67a6", code)
        for forbidden in (
            "ha apps start", "ha apps update", "ha store reload",
            "docker exec", "docker run", "client-encrypted.key",
            "options.json", "ipc-token", "\nmv ", "\nrm ", "\nchmod ",
        ):
            self.assertNotIn(forbidden, code)


if __name__ == "__main__":
    unittest.main()
