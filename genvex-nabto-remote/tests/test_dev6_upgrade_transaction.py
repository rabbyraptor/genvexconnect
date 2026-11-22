"""Offline DEV5-to-DEV6 update transaction tests with a fake Supervisor.

No live network, Docker, HAOS, profile, SDK or account credentials used.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import dev6_upgrade_transaction as tx

TOKEN = "Z" * 43
OPTIONS = {
    "device_id": "123456789012",
    "identity": "fake@example.invalid",
    "unlock_secret": "TEST_ONLY",
    "ipc_token": TOKEN,
    "persistent_session": True,
    "poll_seconds": 60,
    "diagnostic_only": False,
}

OLD_MANIFEST = (
    b'version: "0.1.0-dev6"\nboot: manual_only\nhost_network: false\n'
    b'  persistent_session: bool\n'
)
NEW_MANIFEST = (
    b'version: "0.1.0-dev6"\nboot: manual_only\nhost_network: false\n'
    b'  persistent_session: false\n  persistent_session: bool\n'
)


class FakeUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "genvex_nabto_remote"
        self.stage = self.base / ".genvex-remote-dev6-source-stage"
        self.backup = self.base / ".genvex-remote-dev5-source-backup"
        self.source.mkdir()
        source_files = set(tx.REQUIRED) | {"runtime/polling_service.py"}
        for name in source_files:
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(OLD_MANIFEST if name == "config.yaml" else b"# fixture\n")
        self.archive = self.base / "new.tar.gz"
        self.archive_fixture()
        self.sha = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.state = {
            "version": "0.1.0-dev6",
            "version_latest": "0.1.0-dev6",
            "update_available": False,
            "state": "started",
            "boot": "manual",
            "options": dict(OPTIONS),
        }
        self.actions = []

        def dispatch(args, timeout=120):
            if args[0] == "tar":
                result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
                if result.returncode:
                    raise tx.UpgradeBlocked("TAR_FAILED")
                return result.stdout
            self.actions.append(tuple(args))
            if args[:3] == ["ha", "apps", "info"]:
                return json.dumps({"data": dict(self.state)})
            if args[:3] == ["ha", "apps", "stop"]:
                self.state["state"] = "stopped"
                return ""
            if args == ["ha", "apps", "update", "--help"]:
                return "--backup\n"
            if args == ["ha", "store", "reload"]:
                self.state["version_latest"] = "0.1.0-dev6"
                self.state["update_available"] = True
                return ""
            if args[:3] == ["ha", "apps", "update"]:
                self.state["version"] = "0.1.0-dev6"
                self.state["update_available"] = False
                return ""
            if args[:2] == ["docker", "inspect"]:
                return json.dumps({"State": {"Running": self.state["state"] == "started"}})
            raise AssertionError(args)

        self.dispatch = dispatch
        self.patches = (
            patch.object(tx, "BASE", self.base),
            patch.object(tx, "SOURCE", self.source),
            patch.object(tx, "STAGE", self.stage),
            patch.object(tx, "BACKUP", self.backup),
            patch.object(tx, "command", side_effect=self.dispatch),
            patch.object(tx, "EXPECTED_DEV5", {
                rel: tx.git_blob_sha((self.source / rel).read_bytes())
                for rel in source_files
            }),
        )
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def archive_fixture(self, manifest=NEW_MANIFEST, omit=None):
        names = set(tx.REQUIRED) | {"runtime/polling_service.py"}
        if omit:
            names.remove(omit)
        with tarfile.open(self.archive, "w:gz") as archive:
            for name in sorted(names):
                content = manifest if name == "config.yaml" else b"# fake\n"
                member = tarfile.TarInfo("genvex_nabto_remote/" + name)
                member.size = len(content)
                member.mode = 0o644
                archive.addfile(member, io.BytesIO(content))

    def test_archive_validation(self):
        names = tx.verify_archive(self.archive, self.sha)
        self.assertEqual(len(names), len(tx.REQUIRED) + 1)
        self.assertFalse(self.actions)

    def test_archive_rejects_wrong_sha_and_missing_files(self):
        with self.assertRaises(tx.UpgradeBlocked):
            tx.verify_archive(self.archive, "0" * 64)
        self.archive_fixture(omit="runtime/persistent_rpc45_worker.py")
        changed = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        with self.assertRaises(tx.UpgradeBlocked):
            tx.verify_archive(self.archive, changed)
        self.assertFalse(self.actions)

    def test_preflight_is_readonly(self):
        previous = (self.source / "config.yaml").read_bytes()
        tx.preflight(self.archive, self.sha)
        self.assertEqual(previous, (self.source / "config.yaml").read_bytes())
        self.assertFalse(self.backup.exists())
        self.assertFalse(self.stage.exists())
        self.assertNotIn(("ha", "apps", "stop", tx.APP), self.actions)
        self.assertNotIn(("ha", "apps", "update", tx.APP, "--backup"), self.actions)

    def test_apply_stops_and_updates_once_with_options_unchanged(self):
        tx.apply(self.archive, self.sha)
        self.assertEqual(self.state["version"], tx.NEW_VERSION)
        self.assertEqual(self.state["state"], "stopped")
        self.assertEqual(self.state["options"], OPTIONS)
        self.assertTrue(self.backup.is_dir())
        self.assertIn(OLD_MANIFEST, (self.backup / "config.yaml").read_bytes())
        self.assertEqual((self.source / "config.yaml").read_bytes(), NEW_MANIFEST)
        self.assertFalse(self.stage.exists())
        self.assertEqual(self.actions.count(("ha", "apps", "update", tx.APP, "--backup")), 1)
        self.assertNotIn(("ha", "apps", "start", tx.APP), self.actions)

    def test_invalid_options_refused_before_stop(self):
        self.state["options"]["persistent_session"] = False
        with self.assertRaises(tx.UpgradeBlocked):
            tx.apply(self.archive, self.sha)
        self.assertEqual(self.state["state"], "started")
        self.assertFalse(self.backup.exists())

    def test_changed_old_source_refused(self):
        (self.source / "runtime/persistent_rpc45_worker.py").unlink()
        with self.assertRaises(tx.UpgradeBlocked):
            tx.preflight(self.archive, self.sha)
        self.assertNotIn(("ha", "apps", "stop", tx.APP), self.actions)

    def test_installed_fingerprint_mismatch_refused_before_stop(self):
        (self.source / "runtime/polling_service.py").write_bytes(b"# modified\n")
        with self.assertRaises(tx.UpgradeBlocked) as caught:
            tx.preflight(self.archive, self.sha)
        self.assertEqual(str(caught.exception),
                         "INSTALLED_DEV5_FINGERPRINT_MISMATCH")
        self.assertNotIn(("ha", "apps", "stop", tx.APP), self.actions)

    def test_launcher_is_pinned_and_clears_terminal(self):
        runner = ROOT / "scripts/run_dev6_upgrade_from_deck.sh"
        result = subprocess.run(["bash", "-n", str(runner)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        content = runner.read_text()
        for expected in ("--preflight", "--apply", "SOURCE_COMMIT", "sha256sum",
                         "codeload.github.com", "STEAM_DECK_EXIT_CODE:",
                         "printf '\\033[3J\\033[2J\\033[H'"):
            self.assertIn(expected, content)


if __name__ == "__main__":
    unittest.main()
