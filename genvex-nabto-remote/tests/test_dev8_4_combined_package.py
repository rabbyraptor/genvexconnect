"""DEV8.4.4 combined versioned App+HA bundle test (offline, no HAOS)."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/package_dev8_combined.py"
spec = importlib.util.spec_from_file_location("dev8_combined_packager", SOURCE)
pkg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pkg)


class CombinedPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dest = Path(self.tmp.name) / "dist"
        self.dest.mkdir()
        patches = (
            patch.object(pkg, "DIST", self.dest),
            patch.object(pkg, "ARCHIVE", self.dest / "combined.tar.gz"),
            patch.object(pkg, "SUMS", self.dest / "SHA256SUMS"),
        )
        for one in patches:
            one.start()
            self.addCleanup(one.stop)

    def test_identical_source_produces_byte_identical_single_bundle(self):
        archive, digest, count = pkg.build()
        first = archive.read_bytes()
        self.assertEqual(hashlib.sha256(first).hexdigest(), digest)
        self.assertTrue(30 <= count <= 90)
        assert digest in pkg.SUMS.read_text()
        release = pkg.verify(archive, digest)
        self.assertEqual(release["app_version"], "0.1.0-dev8")
        self.assertEqual(release["home_assistant_version"], "0.2.0")
        self.assertEqual(release["snapshot_schema"], 3)
        self.assertEqual(len(release["rpc45_addresses"]), 17)

        archive2, digest2, count2 = pkg.build()
        self.assertEqual(archive2.read_bytes(), first)
        self.assertEqual((digest2, count2), (digest, count))

    def test_one_archive_contains_both_components_without_private_files(self):
        archive, digest, _ = pkg.build()
        with tarfile.open(archive, "r:gz") as stream:
            names = stream.getnames()
            self.assertIn("DEV8_RELEASE_MANIFEST.json", names)
            self.assertIn("genvex_nabto_remote/config.yaml", names)
            self.assertIn(
                "genvex_nabto_remote/runtime/persistent_rpc45_worker.py",
                names,
            )
            self.assertIn(
                "custom_components/genvex_remote/raw_snapshot_v3.py",
                names,
            )
            self.assertIn(
                "custom_components/genvex_remote/pairing_options.py",
                names,
            )
            self.assertTrue(all(member.isfile() for member in stream))
            self.assertEqual(len(names), len(set(names)))
            self.assertFalse(any(
                name.endswith((".key", ".pem", ".crt", "options.json",
                               "ipc-token", ".db", ".db-wal"))
                or "__pycache__" in name or ".git" in name
                for name in names
            ))
            self.assertEqual(
                next(member.mode for member in stream
                     if member.name == "genvex_nabto_remote/run.sh"),
                0o755,
            )
        self.assertEqual(
            set(pkg.verify(archive, digest)["files"]),
            set(names) - {"DEV8_RELEASE_MANIFEST.json"},
        )

    def test_hash_mismatch_never_validated(self):
        archive, digest, _ = pkg.build()
        archive.write_bytes(archive.read_bytes() + b"tampered")
        with self.assertRaises(pkg.InvalidCombinedPackage):
            pkg.verify(archive, digest)
        with self.assertRaises(pkg.InvalidCombinedPackage):
            pkg.verify(archive, "0" * 64)

    def test_wrong_app_version_rejected_before_build(self):
        duplicate = Path(self.tmp.name) / "app"
        shutil.copytree(pkg.APP, duplicate)
        manifest = duplicate / "config.yaml"
        manifest.write_text(
            manifest.read_text().replace("0.1.0-dev8", "0.1.0-dev6")
        )
        with patch.object(pkg, "APP", duplicate):
            with self.assertRaises(pkg.InvalidCombinedPackage):
                pkg.source_files()

    def test_unexpected_symlink_runtime_file_rejected(self):
        duplicate = Path(self.tmp.name) / "app"
        shutil.copytree(pkg.APP, duplicate)
        link = duplicate / "runtime/unsafe.py"
        link.symlink_to(duplicate / "config.yaml")
        with patch.object(pkg, "APP", duplicate):
            with self.assertRaises(pkg.InvalidCombinedPackage):
                pkg.source_files()


if __name__ == "__main__":
    unittest.main()
