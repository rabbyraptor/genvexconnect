"""Offline guard for language-specific names and canonical default icons."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
HA = ROOT / "experimental/home_assistant/custom_components/genvex_remote"
SOURCE = ROOT / "experimental/genvex_remote"
# Preserve unittest discovery's sys.path: the runtime and HA suites
# have an intentionally duplicate legacy test module filename.
_pre_import_path = list(sys.path)
try:
    sys.path.insert(0, str(SOURCE))
    from register_catalog import (
        RPC45_ALL, RPC45_DEFAULT_ICONS, rpc45_default_icon,
        RPC45Register, ModelProfile, MODEL_PROFILES, rpc45_translation_key,
    )

    module_spec = importlib.util.spec_from_file_location(
        "remote_entity_localizations",
        ROOT / "scripts/sync_remote_entity_localizations.py",
    )
    generator = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(generator)
finally:
    sys.path[:] = _pre_import_path


class RemoteEntityLocalizationTests(unittest.TestCase):
    def test_all_known_entities_have_both_languages(self):
        en = json.loads((HA / "translations/en.json").read_text(encoding="utf-8"))
        da = json.loads((HA / "translations/da.json").read_text(encoding="utf-8"))
        strings = json.loads((HA / "strings.json").read_text(encoding="utf-8"))
        expected = {"supply_air", "outdoor_air", "exhaust_air", "extract_air",
                    "humidity", "data_age", "fan_level"} | {
                        "raw_" + spec.key for spec in RPC45_ALL
                    }
        for catalog in (en, da, strings):
            names = catalog["entity"]["sensor"]
            self.assertEqual(set(names), expected)
            self.assertTrue(all(
                type(names[key]["name"]) is str and names[key]["name"]
                for key in expected
            ))
        self.assertEqual(en, strings)
        self.assertNotEqual(
            en["entity"]["sensor"]["raw_fan_duty_supply"]["name"],
            da["entity"]["sensor"]["raw_fan_duty_supply"]["name"],
        )
        self.assertTrue(
            da["entity"]["sensor"]["raw_fan_duty_supply"]["name"].startswith(
                "RPC45 råværdi 18"
            )
        )
        self.assertTrue(
            en["entity"]["sensor"]["fan_level"]["name"] == "Fan level"
        )

    def test_language_files_generated_from_catalog_not_hand_maintained(self):
        self.assertTrue(generator.check_or_sync(sync=False))

    def test_default_icons_for_every_register_and_unknown_rejected(self):
        self.assertEqual(set(RPC45_DEFAULT_ICONS), {
            spec.key for spec in RPC45_ALL
        })
        self.assertEqual(rpc45_default_icon("humidity"), "mdi:water-percent")
        self.assertEqual(rpc45_default_icon("fan_duty_extract"), "mdi:fan")
        self.assertEqual(rpc45_default_icon("alarm_word_1_raw"),
                         "mdi:alert-outline")
        for spec in RPC45_ALL:
            self.assertTrue(rpc45_default_icon(spec.key).startswith("mdi:"))
        with self.assertRaises(KeyError):
            rpc45_default_icon("unregistered")


    def test_new_model_registers_use_their_own_icon_name_and_namespace(self):
        """A second profile can reuse an address/key without Optima metadata."""
        spec = RPC45Register(
            "supply_air", 20, "Test-profil", "optional",
            name="Second controller supply",
            icon="mdi:hvac",
        )
        model = ModelProfile(
            "fixture280", "Future model fixture", "source: test only",
            (spec,), (), (),
        )
        MODEL_PROFILES["fixture280"] = model
        try:
            self.assertEqual(
                rpc45_translation_key("fixture280", "supply_air"),
                "fixture280_raw_supply_air",
            )
            self.assertEqual(
                rpc45_translation_key("optima270", "supply_air"),
                "raw_supply_air",
            )
            self.assertEqual(
                rpc45_default_icon("supply_air", model_key="fixture280"),
                "mdi:hvac",
            )
            en, da = generator.generated()
            self.assertEqual(
                en["entity"]["sensor"]["fixture280_raw_supply_air"]["name"],
                "RPC45 raw 20 – Second controller supply",
            )
            self.assertEqual(
                da["entity"]["sensor"]["fixture280_raw_supply_air"]["name"],
                "RPC45 råværdi 20 – Test-profil",
            )
        finally:
            MODEL_PROFILES.pop("fixture280", None)

    def test_missing_future_model_metadata_fails_generation(self):
        invalid = RPC45Register("probe", 202, "Probe", "optional")
        MODEL_PROFILES["fixture_invalid"] = ModelProfile(
            "fixture_invalid", "Invalid fixture", "test",
            (invalid,), (), (),
        )
        try:
            with self.assertRaises(ValueError):
                generator.generated()
        finally:
            MODEL_PROFILES.pop("fixture_invalid", None)


if __name__ == "__main__":
    unittest.main()
