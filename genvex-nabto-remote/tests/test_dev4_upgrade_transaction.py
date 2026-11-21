"""DEV4 source/backup transaction tests, all offline with a fake Supervisor.

No HAOS, secrets, device, Docker, network, or real App start/stop.
"""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import dev4_upgrade_transaction as tx

FILES = {
    "Dockerfile": b"FROM scratch\n",
    "run.sh": b"#!/bin/sh\nexit 0\n",
    "config.yaml": (
        b'version: "0.1.0-dev4"\n'
        b"boot: manual_only\n"
        b"host_network: false\n"
        b"  persistent_session: false\n"
        b"  persistent_session: bool\n"
    ),
    "runtime/app_bootstrap.py": b"# fixture\n",
    "runtime/profile_provision.py": b"# fixture\n",
    "runtime/persistent_sdk_adapter.py": b"# fixture\n",
    "runtime/persistent_rpc45_worker.py": b"# fixture\n",
    "runtime/polling_runtime.py": b"# fixture\n",
}


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / "dev4.tar.gz"
        self.make_archive()
        self.sha = hashlib.sha256(self.archive.read_bytes()).hexdigest()

    def make_archive(self, **overrides):
        files = dict(FILES)
        files.update(overrides)
        with tarfile.open(self.archive, "w:gz") as archive:
            for name, data in files.items():
                member = tarfile.TarInfo("genvex_nabto_remote/" + name)
                member.size = len(data)
                member.mode = 0o644
                archive.addfile(member, io.BytesIO(data))

    def test_allows_safe_manifest_and_exact_sha(self):
        names = tx.verify_archive(self.archive, self.sha)
        self.assertEqual(len(names), len(FILES))

    def test_real_packaged_dev4_source_archive_is_accepted(self):
        import importlib.util
        from unittest.mock import patch

        filename = Path(__file__).resolve().parents[2] / "scripts/package_remote_diagnostic_app.py"
        spec = importlib.util.spec_from_file_location("dev4_source_packager", filename)
        packager = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(packager)
        with patch.object(packager, "DEST", self.root), patch.object(
            packager, "ARCHIVE", self.root / "real-dev4-source.tar.gz"
        ):
            real_archive = packager.create_archive()
        checksum = hashlib.sha256(real_archive.read_bytes()).hexdigest()
        names = tx.verify_archive(real_archive, checksum)
        self.assertGreater(len(names), 23)
        self.assertIn("genvex_nabto_remote/runtime/persistent_sdk_adapter.py", names)

    def test_python_without_zlib_uses_system_gzip_for_validation_and_unpack(self):
        from unittest.mock import patch

        original = tarfile.open

        def zlib_missing(*args, **kwargs):
            mode = args[1] if len(args) > 1 else kwargs.get("mode", "r")
            if mode == "r:gz":
                raise tarfile.CompressionError("zlib module is not available")
            return original(*args, **kwargs)

        with patch.object(tx.tarfile, "open", side_effect=zlib_missing):
            names = tx.verify_archive(self.archive, self.sha)
            extracted = tx.unpack(
                self.archive, names, self.root / "uncompressed-extract"
            )
        self.assertEqual(len(names), len(FILES))
        self.assertEqual(
            (extracted / "runtime/persistent_rpc45_worker.py").read_bytes(),
            FILES["runtime/persistent_rpc45_worker.py"],
        )
        self.assertEqual(
            (extracted / "config.yaml").read_bytes(),
            FILES["config.yaml"],
        )

        # The HAOS fallback must rely only on system tar, not on any
        # external gzip executable that is absent from the HAOS host.
        self.assertNotIn("_system_gzip_bytes", tx.open_source_archive.__code__.co_names)

    def test_rejects_tampered_archive(self):
        with self.archive.open("ab") as stream:
            stream.write(b"extra")
        with self.assertRaises(tx.UpgradeBlocked):
            tx.verify_archive(self.archive, self.sha)

    def test_rejects_missing_worker(self):
        files = dict(FILES)
        files.pop("runtime/persistent_rpc45_worker.py")
        with tarfile.open(self.archive, "w:gz") as archive:
            for name, data in files.items():
                item = tarfile.TarInfo("genvex_nabto_remote/" + name)
                item.size = len(data)
                archive.addfile(item, io.BytesIO(data))
        sha = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        with self.assertRaises(tx.UpgradeBlocked):
            tx.verify_archive(self.archive, sha)

    def test_rejects_symlink_entry(self):
        with tarfile.open(self.archive, "w:gz") as archive:
            for name, data in FILES.items():
                member = tarfile.TarInfo("genvex_nabto_remote/" + name)
                if name == "run.sh":
                    member.type = tarfile.SYMTYPE
                    member.linkname = "/tmp/untrusted"
                else:
                    member.size = len(data)
                archive.addfile(member, None if name == "run.sh" else io.BytesIO(data))
        sha = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        with self.assertRaises(tx.UpgradeBlocked):
            tx.verify_archive(self.archive, sha)


class FakeHostTransactionTests(TransactionTests):
    def setUp(self):
        super().setUp()
        self.base = self.root / "apps" / "local"
        self.base.mkdir(parents=True)
        self.source = self.base / "genvex_nabto_remote"
        self.source.mkdir()
        (self.source / "config.yaml").write_text('version: "0.1.0-dev3"\n')
        self.stage = self.base / ".genvex-remote-dev4-source-stage"
        self.backup = self.base / ".genvex-remote-dev3-source-backup"
        self.state = {
            "version": "0.1.0-dev3",
            "version_latest": "0.1.0-dev3",
            "state": "started",
            "boot": "manual",
            "update_available": False,
            "options": {},
        }
        self.actions = []

    def fake_run(self, command, **kwargs):
        self.actions.append(tuple(command))
        if command[:3] == ["ha", "apps", "info"]:
            return json.dumps({"data": dict(self.state)})
        if command[:3] == ["ha", "apps", "stop"]:
            self.state["state"] = "stopped"
            return ""
        if command == ["ha", "apps", "update", "--help"]:
            return "--backup"
        if command[:3] == ["ha", "apps", "update"]:
            self.state["version"] = "0.1.0-dev4"
            self.state["update_available"] = False
            return ""
        if command == ["ha", "store", "reload"]:
            self.state["version_latest"] = "0.1.0-dev4"
            self.state["update_available"] = True
            return ""
        if command[:2] == ["docker", "inspect"]:
            return json.dumps({"State": {"Running": self.state["state"] == "started"}})
        raise AssertionError(command)

    def test_apply_swaps_atomic_and_requests_supervisor_backup_once(self):
        with (
            patch.object(tx, "SOURCE", self.source),
            patch.object(tx, "BASE", self.base),
            patch.object(tx, "STAGE", self.stage),
            patch.object(tx, "BACKUP", self.backup),
            patch.object(tx, "verify_source_tree", return_value=23) as verify,
            patch.object(tx, "run", side_effect=self.fake_run),
            patch.object(tx, "is_app_running", side_effect=lambda: self.state["state"] == "started"),
            patch.object(tx.shutil, "disk_usage", return_value=type("Disk", (), {"free": 1024**3})()),
        ):
            tx.apply(self.archive, self.sha)
        self.assertEqual(verify.call_count, 2)
        self.assertEqual(self.state["version"], "0.1.0-dev4")
        self.assertEqual(self.state["state"], "stopped")
        self.assertTrue(self.backup.is_dir())
        self.assertIn("0.1.0-dev3", (self.backup / "config.yaml").read_text())
        self.assertIn("0.1.0-dev4", (self.source / "config.yaml").read_text())
        self.assertTrue((self.source / "runtime/persistent_sdk_adapter.py").is_file())
        self.assertFalse(self.stage.exists())
        self.assertEqual(self.actions.count(("ha", "apps", "update", tx.SLUG, "--backup")), 1)
        self.assertNotIn(("ha", "apps", "start", tx.SLUG), self.actions)

    def test_bad_hash_fails_before_stop_or_swap(self):
        with (
            patch.object(tx, "SOURCE", self.source),
            patch.object(tx, "BASE", self.base),
            patch.object(tx, "STAGE", self.stage),
            patch.object(tx, "BACKUP", self.backup),
            patch.object(tx, "run", side_effect=self.fake_run),
        ):
            with self.assertRaises(tx.UpgradeBlocked):
                tx.apply(self.archive, "0" * 64)
        self.assertEqual(self.actions, [])
        self.assertTrue(self.source.exists())
        self.assertFalse(self.backup.exists())


if __name__ == "__main__":
    unittest.main()
