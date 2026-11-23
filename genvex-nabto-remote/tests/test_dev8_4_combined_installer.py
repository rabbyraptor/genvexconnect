"""DEV9.4.5 combined installer acceptance with fake HAOS / Supervisor.

Uses a real deterministic combined archive and host tar CLI but directs all
filesystem mutations into a temporary directory. No HAOS or Nabto I/O.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


pkg = load_file("dev9_package_for_host_test",
                ROOT / "scripts/package_dev9_combined.py")
installer = load_file("dev9_host_installer",
                      ROOT / "scripts/install_dev9_combined.py")


class CombinedInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app_base = self.root / "apps"
        self.ha_home = self.root / "homeassistant"
        self.source_app = self.app_base / "genvex_nabto_remote"
        self.source_ha = self.ha_home / "custom_components/genvex_remote"
        self.source_app.mkdir(parents=True)
        self.source_ha.mkdir(parents=True)
        (self.source_app / "config.yaml").write_text(
            'version: "0.1.0-dev8"\n'
        )
        (self.source_app / "original.txt").write_text("OLD_APP")
        (self.source_ha / "manifest.json").write_text(
            '{"domain":"genvex_remote","version":"0.1.1"}'
        )
        (self.source_ha / "original.py").write_text("OLD_HA")
        self.distrib = self.root / "dist"
        self.distrib.mkdir()
        self.state = {
            "version": "0.1.0-dev8",
            "version_latest": "0.1.0-dev8",
            "state": "started",
            "boot": "manual",
            "update_available": False,
            "options": {
                "identity": "fake@example.invalid",
                "device_id": "123456789012",
                "ipc_token": "X" * 43,
                "unlock_secret": "FAKE_ONLY",
                "persistent_session": True,
                "poll_seconds": 60,
                "diagnostic_only": False,
            },
        }
        self.events = []
        self.fail = None

        def fake_command(args, timeout=120):
            argv = tuple(args)
            self.events.append(argv)
            if args[0] == "tar":
                done = subprocess.run(args, capture_output=True,
                                      text=True, timeout=timeout)
                if done.returncode:
                    raise installer.ReleaseBlocked("TAR_FAILED")
                return done.stdout
            if argv == ("ha", "apps", "update", "--help"):
                return "--backup\n"
            if argv[:3] == ("ha", "apps", "info"):
                return json.dumps({"data": dict(self.state)})
            if argv == ("ha", "core", "info", "--raw-json"):
                return json.dumps({"data": {
                    "version": "2026.11.1", "port": 8123, "ssl": False,
                }})
            if argv == ("ha", "apps", "stop", installer.APP_SLUG):
                self.state["state"] = "stopped"
                return ""
            if argv == ("ha", "store", "reload"):
                self.state["version_latest"] = "0.1.0-dev9"
                self.state["update_available"] = True
                return ""
            if argv == ("ha", "apps", "update", installer.APP_SLUG, "--backup"):
                if self.fail == "update":
                    raise installer.ReleaseBlocked("SIMULATED_APP_UPDATE_FAILED")
                self.state["version"] = "0.1.0-dev9"
                self.state["update_available"] = False
                self.state["options"].setdefault("raw_registers_v3", False)
                self.state["options"].setdefault("fan_level_v4", False)
                return ""
            if argv == ("ha", "apps", "start", installer.APP_SLUG):
                self.state["state"] = "started"
                return ""
            if argv == ("ha", "core", "check"):
                if self.fail == "core_check":
                    raise installer.ReleaseBlocked("SIMULATED_CORE_CHECK_FAILED")
                return ""
            if argv == ("ha", "core", "restart"):
                return ""
            raise AssertionError("Unexpected fake HAOS command:" + repr(argv))

        self.fake_command = fake_command
        self.patches = [
            patch.object(pkg, "DIST", self.distrib),
            patch.object(pkg, "ARCHIVE", self.distrib / "dev9.tar.gz"),
            patch.object(pkg, "SUMS", self.distrib / "SUMS"),
            patch.object(installer, "BASE", self.app_base),
            patch.object(installer, "HA_HOME", self.ha_home),
            patch.object(installer, "APP_SOURCE", self.source_app),
            patch.object(installer, "HA_SOURCE", self.source_ha),
            patch.object(installer, "APP_BACKUP", self.app_base / ".backup-dev9"),
            patch.object(installer, "HA_BACKUP", self.ha_home / ".backup-dev9"),
            patch.object(installer, "APP_STAGE", self.app_base / ".stage-dev9"),
            patch.object(installer, "HA_STAGE", self.ha_home / ".stage-dev9"),
            patch.object(installer, "command", side_effect=self.fake_command),
            patch.object(installer, "core_api_ready", return_value=True),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.archive, self.sha, _ = pkg.build()

    def test_real_dev9_bundle_validates_without_host_mutation(self):
        before_app = (self.source_app / "config.yaml").read_bytes()
        before_ha = (self.source_ha / "manifest.json").read_bytes()
        files = installer.verify_bundle(self.archive, self.sha)
        self.assertGreater(len(files), 30)
        self.assertIn("custom_components/genvex_remote/raw_snapshot_v3.py", files)
        installer.installed_preflight(files)
        self.assertEqual(before_app, (self.source_app / "config.yaml").read_bytes())
        self.assertEqual(before_ha, (self.source_ha / "manifest.json").read_bytes())
        self.assertFalse(installer.APP_STAGE.exists())
        self.assertFalse(installer.HA_STAGE.exists())
        self.assertFalse(installer.APP_BACKUP.exists())
        self.assertFalse(installer.HA_BACKUP.exists())
        self.assertFalse(any("stop" in cmd or "restart" in cmd
                             for cmd in self.events if cmd and cmd[0] == "ha"))

    def test_single_bundle_upgrades_app_and_ha_once(self):
        installer.apply(self.archive, self.sha)
        self.assertEqual(self.state["version"], "0.1.0-dev9")
        self.assertEqual(self.state["state"], "started")
        self.assertEqual(self.state["options"]["raw_registers_v3"], False)
        self.assertEqual(
            (self.source_ha / "manifest.json").read_text().count('"0.3.0"'), 1
        )
        self.assertTrue((self.source_app / "runtime/raw_registers_v3.py").is_file())
        self.assertTrue((self.source_app / "runtime/raw_snapshot_v4.py").is_file())
        self.assertTrue((self.source_ha / "raw_snapshot_v3.py").is_file())
        self.assertTrue((self.source_ha / "raw_snapshot_v4.py").is_file())
        self.assertTrue((installer.APP_BACKUP / "original.txt").is_file())
        self.assertTrue((installer.HA_BACKUP / "original.py").is_file())
        self.assertFalse(installer.APP_STAGE.exists())
        self.assertFalse(installer.HA_STAGE.exists())
        self.assertEqual(self.events.count(
            ("ha", "apps", "update", installer.APP_SLUG, "--backup")), 1)
        self.assertEqual(self.events.count(("ha", "core", "restart")), 1)

    def test_corrupt_sha_blocks_before_supervisor_or_stop(self):
        with self.assertRaises(installer.ReleaseBlocked):
            installer.apply(self.archive, "f" * 64)
        self.assertEqual(self.events, [])
        self.assertTrue((self.source_ha / "original.py").is_file())

    def test_supervisor_update_failure_restores_old_app_source(self):
        self.fail = "update"
        with self.assertRaises(installer.ReleaseBlocked):
            installer.apply(self.archive, self.sha)
        self.assertEqual(self.state["version"], "0.1.0-dev8")
        self.assertEqual(self.state["state"], "started")
        self.assertTrue((self.source_app / "original.txt").is_file())
        self.assertTrue((self.source_ha / "original.py").is_file())
        self.assertFalse(installer.APP_BACKUP.exists())
        self.assertFalse(installer.HA_BACKUP.exists())

    def test_core_check_failure_restores_ha_source_and_keeps_dev9_app(self):
        self.fail = "core_check"
        with self.assertRaises(installer.ReleaseBlocked):
            installer.apply(self.archive, self.sha)
        self.assertEqual(self.state["version"], "0.1.0-dev9")
        self.assertEqual(self.state["state"], "started")
        self.assertTrue((self.source_ha / "original.py").is_file())
        self.assertFalse(installer.HA_BACKUP.exists())
        self.assertTrue((installer.APP_BACKUP / "original.txt").is_file())
        self.assertEqual(self.events.count(("ha", "core", "restart")), 1)

    def test_never_prints_credential_contents(self):
        from contextlib import redirect_stdout
        import io
        stream = io.StringIO()
        with redirect_stdout(stream):
            installer.installed_preflight(
                installer.verify_bundle(self.archive, self.sha)
            )
        output = stream.getvalue()
        self.assertNotIn(self.state["options"]["ipc_token"], output)
        self.assertNotIn("FAKE_ONLY", output)
        self.assertNotIn("fake@example.invalid", output)


if __name__ == "__main__":
    unittest.main()
