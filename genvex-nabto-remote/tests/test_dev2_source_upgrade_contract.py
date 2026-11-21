"""Offline contract of source-only, no-secret dev1 -> dev2 host transaction."""
from __future__ import annotations

import importlib.util
import hashlib
import os
import shutil
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
        # Historical dev1 -> dev2 tests retain an isolated dev2 fixture.
        # The actual App source has advanced to the dev3 candidate.
        self.legacy_source = self.root / "legacy-dev2-source"
        shutil.copytree(packager.SOURCE, self.legacy_source)
        manifest = self.legacy_source / "config.yaml"
        manifest.write_text(
            manifest.read_text().replace('version: "0.1.0-dev3"',
                                         'version: "0.1.0-dev2"')
        )
        with (
            patch.object(packager, "SOURCE", self.legacy_source),
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
        self.assertIn("sha256sum -c >/dev/null", remote)
        self.assertNotIn("sha256sum -c --status", remote)
        self.assertIn("mv $SRC $BACKUP", remote)
        self.assertIn("mv $STAGE/genvex_nabto_remote $SRC", remote)
        for forbidden in (
            "ha store reload", "ha apps update", "ha apps install",
            "ha apps start", "ha apps stop", "docker start", "docker run",
            "/apps/data", "client-encrypted.key", "ipc-token",
        ):
            self.assertNotIn(forbidden, remote)

    def isolated_transaction(self, *, fail_promotion=False):
        # Execute the actual generated remote shell transaction against a
        # temporary source tree; never SSH or touch the host's HAOS paths.
        base = self.root / "isolated-local-app-source"
        base.mkdir()
        old = base / "genvex_nabto_remote"
        old.mkdir()
        (old / "config.yaml").write_text('version: "0.1.0-dev1"\n')
        prior_hash = hashlib.sha256((old / "config.yaml").read_bytes()).hexdigest()
        prior_files = {
            "Dockerfile": "5c7edfb109ccad4b09a19ff28c3173e405bcb33eb26034174ee10de83d2f4cdd",
            "run.sh": "50c68a9defb3c47621ab6d3b901b3e645ac19f539616457f469a1cb76a91f398",
            "runtime/app_bootstrap.py": "9e8862450d6204d21136baae25ce37aa24aa591f1008842c5914911517db7db1",
            "runtime/profile_provision.py": "3d35505bfc12b24cc0f68e0a437c6fce047ffe2613ab13ccb10fe2959ec1fe82",
        }
        (old / "runtime").mkdir()
        fake_digests = {}
        for relative, known in prior_files.items():
            target = old / relative
            target.write_text("FAKE " + relative)
            fake_digests[known] = hashlib.sha256(target.read_bytes()).hexdigest()
        data = self.root / "private-app-data"
        data.mkdir()
        (data / "sentinel").write_text("DO NOT MODIFY")
        source = SCRIPT.read_text().replace(
            "/mnt/data/supervisor/apps/local", str(base)
        ).replace(
            "5c15ac644063f1a0fbcbcc3fd2050a56715922bf7f7f5640032b6f49bcdbfaac",
            prior_hash,
        )
        for expected_digest, fake_digest in fake_digests.items():
            source = source.replace(expected_digest, fake_digest)
        local_script = self.root / "isolated-transaction.sh"
        local_script.write_text(source)
        (self.bin / "ssh").write_text(
            "#!/bin/bash\n"
            "last=${!#}\n"
            "case \"$last\" in\n"
            "  'sh -s -- --execute-readonly') cat >/dev/null; exit 0 ;;\n"
            "  'sh -c '* ) exec sh -c \"$last\" ;;\n"
            "  *) exit 8 ;;\n"
            "esac\n"
        )
        (self.bin / "ssh").chmod(0o700)
        (self.bin / "ha").write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' 'state: stopped' 'boot: manual' 'version: 0.1.0-dev1'\n"
        )
        (self.bin / "ha").chmod(0o700)
        (self.bin / "docker").write_text("#!/bin/sh\nexit 1\n")
        (self.bin / "docker").chmod(0o700)
        # Emulate BusyBox on the remote side: it supports -c -s but
        # rejects GNU long-form --status when checking stdin digests.
        (self.bin / "sha256sum").write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = -c ] && [ \"$2\" = --status ] && "
            "[ \"$#\" -eq 2 ]; then\n"
            "  echo 'BusyBox does not support --status' >&2\n"
            "  exit 2\n"
            "fi\n"
            "exec /usr/bin/sha256sum \"$@\"\n"
        )
        (self.bin / "sha256sum").chmod(0o700)
        if fail_promotion:
            (self.bin / "mv").write_text(
                "#!/bin/sh\n"
                "case \"$1\" in *dev2-source-stage/genvex_nabto_remote)"
                " echo 'SIMULATED PROMOTION FAILURE' >&2; exit 3 ;; esac\n"
                "exec /bin/mv \"$@\"\n"
            )
            (self.bin / "mv").chmod(0o700)
        run = subprocess.run(
            ["bash", str(local_script), "--apply", str(self.archive),
             str(self.artifacts / "APP_SOURCE_SHA256SUMS")],
            capture_output=True, text=True, env=self.env, timeout=20,
        )
        return run, old, base, data

    def test_isolated_source_swap_retains_old_backup(self):
        run, source, base, data = self.isolated_transaction()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        backup = base / ".genvex-remote-dev1-source-backup"
        self.assertTrue(backup.is_dir())
        self.assertEqual((backup / "config.yaml").read_text(),
                         'version: "0.1.0-dev1"\n')
        self.assertIn('version: "0.1.0-dev2"',
                      (source / "config.yaml").read_text())
        self.assertFalse((base / ".genvex-remote-dev2-source-stage").exists())
        self.assertEqual((data / "sentinel").read_text(), "DO NOT MODIFY")

    def test_isolated_rename_failure_restores_original_source(self):
        run, source, base, data = self.isolated_transaction(
            fail_promotion=True
        )
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual((source / "config.yaml").read_text(),
                         'version: "0.1.0-dev1"\n')
        self.assertFalse(
            (base / ".genvex-remote-dev1-source-backup").exists()
        )
        self.assertFalse(
            (base / ".genvex-remote-dev2-source-stage").exists()
        )
        self.assertEqual((data / "sentinel").read_text(), "DO NOT MODIFY")

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
