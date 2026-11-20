"""Offline contract of source-only, no-secret dev1 -> dev2 host transaction."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/upgrade_remote_local_app_source_dev2.sh"
GATE = ROOT / "scripts/audit_haos_dev2_source_transaction_preflight_v1.sh"
PACKAGER = ROOT / "scripts/package_remote_diagnostic_app.py"
spec = importlib.util.spec_from_file_location("upgrade_packager_test", PACKAGER)
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class Dev2UpgradeContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.artifacts = self.root / "dist"
        self.artifacts.mkdir()
        with (
            patch.object(packager, "DEST", self.artifacts),
            patch.object(
                packager, "ARCHIVE",
                self.artifacts / "genvex-nabto-remote-local-app-source.tar.gz"
            ),
        ):
            self.archive = packager.create_archive()
        (self.artifacts / GATE.name).write_bytes(GATE.read_bytes())

        self.home = self.root / "home"
        (self.home / ".ssh").mkdir(parents=True)
        (self.home / ".ssh" / "id_ed25519").write_text("FAKE TEST IDENTITY")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.calls = self.root / "calls.txt"
        fake = self.bin / "ssh"
        fake.write_text(
            "#!/bin/sh\n"
            "printf 'CALL:%s\\n' \"$*\" >> \"$FAKE_SSH_CALLS\"\n"
            "if [ \"$FAKE_SSH_EXIT\" = failure ]; then exit 9; fi\n"
            "cat >/dev/null\n"
            "echo 'PASS: mocked SSH transport only'\n"
        )
        fake.chmod(0o700)
        self.env = os.environ.copy()
        self.env["HOME"] = str(self.home)
        self.env["PATH"] = str(self.bin) + os.pathsep + self.env["PATH"]
        self.env["FAKE_SSH_CALLS"] = str(self.calls)
        self.env["FAKE_SSH_EXIT"] = "success"

    def run_script(self, mode: str):
        return subprocess.run(
            ["bash", str(SCRIPT), mode, str(self.archive),
             str(self.artifacts / "APP_SOURCE_SHA256SUMS")],
            capture_output=True, text=True, env=self.env, timeout=20,
        )

    def test_shell_syntax(self):
        result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_preflight_never_issues_remote_write(self):
        result = self.run_script("--preflight")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("preflight complete; no HAOS files changed", result.stdout)
        calls = self.calls.read_text().split("CALL:")[1:]
        self.assertEqual(len(calls), 1)
        self.assertIn("sh -s -- --execute-readonly", calls[0])
        self.assertNotIn("sh -c", calls[0])

    def test_explicit_apply_requires_passed_readonly_gate(self):
        self.env["FAKE_SSH_EXIT"] = "failure"
        result = self.run_script("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.calls.read_text().split("CALL:")[1:]), 1)

    def test_apply_reaches_only_dedicated_source_transaction(self):
        result = self.run_script("--apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = self.calls.read_text().split("CALL:")[1:]
        self.assertEqual(len(calls), 2)
        self.assertIn("sh -s -- --execute-readonly", calls[0])
        remote = calls[1]
        self.assertIn("sh -c", remote)
        self.assertIn(".genvex-remote-dev1-source-backup", remote)
        self.assertIn(".genvex-remote-dev2-source-stage", remote)
        self.assertIn("sha256sum -c --status", remote)
        self.assertIn("mv $SRC $BACKUP", remote)
        self.assertIn("mv $STAGE/genvex_nabto_remote $SRC", remote)
        for forbidden in (
            "ha store reload", "ha apps update", "ha apps install",
            "ha apps start", "ha apps stop", "docker start", "docker run",
            "/apps/data", "client-encrypted.key", "ipc-token",
        ):
            self.assertNotIn(forbidden, remote)

    def test_refuse_invalid_archive_before_ssh(self):
        with self.archive.open("ab") as stream:
            stream.write(b"TAMPERED")
        result = self.run_script("--preflight")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checksum mismatch", result.stdout)
        self.assertFalse(self.calls.exists())

    def test_archive_contains_only_known_dev2_source_files(self):
        with tarfile.open(self.archive, "r:gz") as archive:
            manifest = archive.extractfile("genvex_nabto_remote/config.yaml").read()
            self.assertIn(b'version: "0.1.0-dev2"', manifest)
            self.assertTrue(all(m.isfile() for m in archive.getmembers()))
            self.assertNotIn(
                "genvex_nabto_remote/options.json",
                archive.getnames(),
            )


if __name__ == "__main__":
    unittest.main()
