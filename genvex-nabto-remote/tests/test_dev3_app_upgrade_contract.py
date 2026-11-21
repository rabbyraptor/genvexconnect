"""Offline dev2 -> dev3 local App upgrade controls (no HAOS, no secrets)."""
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
PACKAGE = ROOT / "scripts/package_remote_diagnostic_app.py"
SRC_SWAP = ROOT / "scripts/upgrade_remote_local_app_source_dev3.sh"
READ_GATE = ROOT / "scripts/audit_haos_dev3_source_transaction_preflight_v1.sh"
SUPERVISOR = ROOT / "scripts/update_haos_genvex_remote_dev3_with_backup_v1.sh"
spec = importlib.util.spec_from_file_location("dev3_packager", PACKAGE)
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class Dev3AppUpgradeContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.dist = self.root / "dist"
        self.dist.mkdir()
        with (patch.object(packager, "DEST", self.dist),
              patch.object(packager, "ARCHIVE",
                           self.dist / "genvex-nabto-remote-local-app-source.tar.gz")):
            self.archive = packager.create_archive()
        (self.dist / READ_GATE.name).write_bytes(READ_GATE.read_bytes())

        self.home = self.root / "home"
        self.home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.calls = self.root / "ssh.calls"
        stub = self.bin / "ssh"
        stub.write_text(
            "#!/bin/sh\n"
            "printf 'CALL:%s\\n' \"$*\" >> \"$TEST_SSH_CALLS\"\n"
            "if [ \"$TEST_SSH_FAIL\" = yes ]; then exit 7; fi\n"
            "cat >/dev/null\n"
            "echo 'PASS: fake SSH transport'\n"
        )
        stub.chmod(0o700)
        self.env = os.environ.copy()
        self.env["HOME"] = str(self.home)
        self.env["PATH"] = str(self.bin) + os.pathsep + self.env["PATH"]
        self.env["TEST_SSH_CALLS"] = str(self.calls)
        self.env["TEST_SSH_FAIL"] = "no"

    def run_source(self, mode):
        return subprocess.run(
            ["bash", str(SRC_SWAP), mode, str(self.archive),
             str(self.dist / "APP_SOURCE_SHA256SUMS")],
            capture_output=True, text=True, env=self.env, timeout=20,
        )

    def test_upgrade_scripts_shell_syntax(self):
        for script in (SRC_SWAP, READ_GATE, SUPERVISOR):
            check = subprocess.run(["bash", "-n", str(script)],
                                   capture_output=True, text=True)
            self.assertEqual(check.returncode, 0, str(script) + check.stderr)

    def test_dev3_archive_is_source_only_and_versioned(self):
        with tarfile.open(self.archive, "r:gz") as handle:
            members = handle.getmembers()
            self.assertTrue(members)
            self.assertTrue(all(m.isfile() for m in members))
            self.assertFalse(any(".key" in m.name or ".crt" in m.name
                                 or "options.json" in m.name
                                 for m in members))
            config = handle.extractfile("genvex_nabto_remote/config.yaml").read()
            self.assertIn(b'version: "0.1.0-dev3"', config)
            self.assertIn(b"boot: manual_only", config)
            self.assertIn(b"host_network: false", config)

    def test_preflight_calls_only_remote_readonly_gate(self):
        result = self.run_source("--preflight")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = self.calls.read_text().split('CALL:')[1:]
        self.assertEqual(len(calls), 1)
        self.assertIn("sh -s -- --execute-readonly", calls[0])
        self.assertNotIn("sh -c", calls[0])

    def test_apply_runs_readonly_before_single_source_swap(self):
        result = self.run_source("--apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = self.calls.read_text().split('CALL:')[1:]
        self.assertEqual(len(calls), 2)
        self.assertIn("sh -s -- --execute-readonly", calls[0])
        self.assertIn("sh -c", calls[1])
        self.assertIn(".genvex-remote-dev2-source-backup", calls[1])
        self.assertIn(".genvex-remote-dev3-source-stage", calls[1])
        self.assertIn("mv $SRC $BACKUP", calls[1])
        for forbidden in ("ha apps update", "ha store reload", "ha apps start",
                          "/apps/data", "client-encrypted.key", "ipc-token"):
            self.assertNotIn(forbidden, calls[1])

    def test_remote_preflight_failure_blocks_swap(self):
        self.env["TEST_SSH_FAIL"] = "yes"
        result = self.run_source("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.calls.read_text().split('CALL:')[1:]), 1)

    def test_checksum_tamper_blocks_before_ssh(self):
        with self.archive.open("ab") as f:
            f.write(b"TAMPER")
        result = self.run_source("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.calls.exists())

    def test_supervisor_update_is_opt_in_backup_enabled_and_no_start(self):
        content = SUPERVISOR.read_text()
        self.assertIn("ha store reload", content)
        self.assertIn("ha apps update local_genvex_nabto_remote --backup", content)
        self.assertIn("version_latest", content)
        self.assertIn(".genvex-remote-dev2-source-backup", content)
        for forbidden in ("/apps/data", "ha apps start", "docker start",
                          "client-encrypted.key", "ipc-token"):
            self.assertNotIn(forbidden, content)
        result = subprocess.run(["sh", str(SUPERVISOR), "--preflight"],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("inert preflight", result.stdout)


if __name__ == "__main__":
    unittest.main()
