"""Fake-HAOS acceptance tests for the single pinned Genvex integration installer."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/install_unified_ha_integration.py"
spec = importlib.util.spec_from_file_location("unified_ha_installer", SCRIPT)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class UnifiedInstallerTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.base = Path(self.work.name)
        self.components = self.base / "custom_components"
        self.components.mkdir()
        self.existing = self.components / "genvex_remote"
        self.existing.mkdir()
        (self.existing / "manifest.json").write_text(
            '{"domain":"genvex_remote","version":"0.1.0"}'
        )
        (self.existing / "original.py").write_text("ORIGINAL = True\n")
        self.archive = self.base / "source.tar.gz"
        self.create_archive()
        self.sha = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.calls = []

        def fake_ha(*args, **kwargs):
            self.calls.append(args)
            if args[:2] == ("core", "info"):
                return json.dumps({"data": {"state": "started"}})
            return ""

        self.fake_ha = fake_ha
        self.patchers = [
            patch.object(installer, "COMPONENTS", self.components),
            patch.object(installer, "TARGET", self.existing),
            patch.object(installer, "BACKUP",
                         self.components / ".genvex_remote_pre_unified_backup"),
            patch.object(installer, "STAGE",
                         self.components / ".genvex_remote_unified_stage"),
            patch.object(installer, "ha_cli", side_effect=self.fake_ha),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def create_archive(self, extra: tuple[str, bytes] | None = None):
        files = {
            name: b"MARKER = True\n" for name in (
                "__init__.py", "config_flow.py", "pairing_options.py",
                "core_supervisor_loader.py", "supervisor_pairing.py",
                "runtime_client.py", "coordinator.py", "sensor.py",
                "snapshot.py", "const.py",
            )
        }
        files["manifest.json"] = (
            b'{"domain":"genvex_remote","config_flow":true,"version":"0.1.0"}'
        )
        files["translations/da.json"] = b'{"config":{}}'
        if extra:
            files[extra[0]] = extra[1]
        with tarfile.open(self.archive, "w:gz") as bundle:
            for name, body in sorted(files.items()):
                arc = f"genvex_remote/{name}"
                meta = tarfile.TarInfo(arc)
                meta.size = len(body)
                meta.mode = 0o644
                bundle.addfile(meta, io.BytesIO(body))

    def test_one_transaction_restarts_once_and_keeps_prior_source(self):
        installer.apply(self.archive, self.sha)
        backup = self.components / ".genvex_remote_pre_unified_backup"
        self.assertTrue((backup / "original.py").is_file())
        self.assertTrue((self.existing / "pairing_options.py").is_file())
        self.assertFalse((self.existing / "original.py").exists())
        self.assertFalse((self.components / ".genvex_remote_unified_stage").exists())
        self.assertEqual(self.calls.count(("core", "check")), 1)
        self.assertEqual(self.calls.count(("core", "restart")), 1)

    def test_actual_component_archive_generated_by_operator_is_accepted(self):
        """Do not validate only fake fixtures: inspect every real deployed file."""
        import gzip
        source = ROOT / "experimental/home_assistant/custom_components/genvex_remote"
        files = sorted(
            p for p in source.rglob("*")
            if p.is_file() and p.suffix in (".py", ".json")
        )
        self.assertGreaterEqual(len(files), 9)
        with self.archive.open("wb") as stream:
            with gzip.GzipFile(filename="", fileobj=stream,
                               mode="wb", mtime=0) as zipped:
                with tarfile.open(fileobj=zipped, mode="w",
                                  format=tarfile.PAX_FORMAT) as bundle:
                    for file in files:
                        arc = "genvex_remote/" + file.relative_to(source).as_posix()
                        info = bundle.gettarinfo(str(file), arcname=arc)
                        info.mtime = 0
                        info.uid = info.gid = 0
                        info.uname = info.gname = ""
                        info.mode = 0o644
                        with file.open("rb") as content:
                            bundle.addfile(info, content)
        digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        accepted = installer.check_archive(self.archive, digest)
        self.assertEqual(len(accepted), len(files))

    def test_wrong_archive_sha_refused_without_mutation(self):
        with self.assertRaises(installer.InstallBlocked) as caught:
            installer.apply(self.archive, "0" * 64)
        self.assertEqual(str(caught.exception), "ARCHIVE_SHA256_MISMATCH")
        self.assertTrue((self.existing / "original.py").is_file())
        self.assertEqual(self.calls, [])

    def test_json_and_utf8_failures_have_specific_categories(self):
        for invalid, expected in (
            (("strings.json", b'{"bad":}'), "ARCHIVE_JSON_INVALID"),
            (("strings.json", b"\xff"), "ARCHIVE_UTF8_INVALID"),
        ):
            self.create_archive(extra=invalid)
            digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
            with self.subTest(expected=expected):
                with self.assertRaises(installer.InstallBlocked) as caught:
                    installer.check_archive(self.archive, digest)
                self.assertEqual(str(caught.exception), expected)

    def test_installer_uses_core_check_for_source_syntax(self):
        """The host cannot be required to use HA Core's newer Python grammar."""
        source = SCRIPT.read_text()
        self.assertNotIn("ast.parse(", source)
        self.assertIn('ha_cli("core", "check"', source)

    def test_traversal_and_symlinks_refused(self):
        self.create_archive(extra=("../escape.py", b"BAD = True\n"))
        sha = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        with self.assertRaises(installer.InstallBlocked):
            installer.check_archive(self.archive, sha)
        self.create_archive(extra=("evil.py", b"BAD = True\n"))
        with tarfile.open(self.archive, "a" if False else "w:gz") as out:
            link = tarfile.TarInfo("genvex_remote/link.py")
            link.type = tarfile.SYMTYPE
            link.linkname = "/etc/passwd"
            out.addfile(link)
        sha = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        with self.assertRaises(installer.InstallBlocked):
            installer.check_archive(self.archive, sha)

    def test_core_check_failure_restores_previous_component(self):
        def fail_check(*args, **kwargs):
            self.calls.append(args)
            if args == ("core", "check"):
                raise installer.InstallBlocked("HA_CORE_CHECK_FAILED")
            if args[:2] == ("core", "info"):
                return '{"data":{"state":"started"}}'
            return ""

        with patch.object(installer, "ha_cli", side_effect=fail_check):
            with self.assertRaises(installer.InstallBlocked):
                installer.apply(self.archive, self.sha)
        self.assertTrue((self.existing / "original.py").is_file())
        self.assertFalse(
            (self.components / ".genvex_remote_pre_unified_backup").exists()
        )
        self.assertEqual(self.calls.count(("core", "restart")), 1)

    def test_operator_launcher_clears_screen_and_pins_source(self):
        path = ROOT / "scripts/run_unified_ha_install_from_deck.sh"
        result = subprocess.run(["bash", "-n", str(path)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        source = path.read_text()
        for text in (
            "PINNED_COMMIT", "SOURCE_COMMIT:", "COMPONENT_SHA256:",
            "install_unified_ha_integration.py", "STEAM_DECK_EXIT_CODE:",
            r"printf '\033[3J\033[2J\033[H'",
        ):
            self.assertIn(text, source)


if __name__ == "__main__":
    unittest.main()
