"""Isolated filesystem contracts for atomic Genvex remote component install."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import haos_install_remote_component as installer


class ComponentInstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source = root / "src"
        self.config = root / "config"
        self.source.mkdir()
        self.config.mkdir()
        for name in installer.FILES:
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if name == "manifest.json":
                path.write_text(json.dumps({
                    "domain": "genvex_remote", "config_flow": True,
                }))
            elif name.endswith(".py"):
                path.write_text("pass\n")
            elif name in ("strings.json", "translations/en.json", "translations/da.json"):
                path.write_text(json.dumps({"entity": {"sensor": {
                    k: {"name": k} for k in (
                        "supply_air", "outdoor_air", "exhaust_air",
                        "extract_air", "humidity"
                    )}}}))
            else:
                path.write_text("{}\\n")

    def test_dry_run_does_not_create_directory(self):
        self.assertEqual(installer.install(self.source, self.config, apply=False),
                         "PASS: REMOTE_COMPONENT_PREFLIGHT_ONLY")
        self.assertFalse((self.config / "custom_components").exists())

    def test_install_creates_exact_files_atomically(self):
        self.assertIn("INSTALLED", installer.install(self.source, self.config, apply=True))
        target = self.config / "custom_components" / "genvex_remote"
        self.assertTrue(target.is_dir())
        for name in installer.FILES:
            self.assertEqual((target / name).read_bytes(),
                             (self.source / name).read_bytes())
        with self.assertRaises(ValueError):
            installer.install(self.source, self.config, apply=True)

    def test_rejects_existing_lan_untouched(self):
        parent = self.config / "custom_components"
        (parent / "genvex").mkdir(parents=True)
        (parent / "genvex" / "marker").write_text("keep")
        installer.install(self.source, self.config, apply=True)
        self.assertEqual((parent / "genvex" / "marker").read_text(), "keep")

    def test_rejects_missing_and_symlinked_sources(self):
        (self.source / "sensor.py").unlink()
        with self.assertRaises(ValueError):
            installer.install(self.source, self.config, apply=False)
        (self.source / "sensor.py").symlink_to(self.source / "const.py")
        with self.assertRaises(ValueError):
            installer.install(self.source, self.config, apply=True)

    def test_missing_english_fallback_blocks_install(self):
        (self.source / "translations/en.json").unlink()
        with self.assertRaises(ValueError):
            installer.install(self.source, self.config, apply=True)
        self.assertFalse((self.config / "custom_components/genvex_remote").exists())

    def test_inconsistent_language_keys_block_install(self):
        (self.source / "translations/da.json").write_text(
            json.dumps({"entity": {"sensor": {"humidity": {"name": "Luftfugtighed"}}}})
        )
        with self.assertRaises(ValueError):
            installer.install(self.source, self.config, apply=False)

    def test_rejects_invalid_manifest(self):
        (self.source / "manifest.json").write_text('{"domain":"genvex"}')
        with self.assertRaises(ValueError):
            installer.install(self.source, self.config, apply=False)


if __name__ == "__main__":
    unittest.main()
