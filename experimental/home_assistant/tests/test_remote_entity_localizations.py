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
sys.path.insert(0, str(SOURCE))
from register_catalog import RPC45_ALL, RPC45_DEFAULT_ICONS, rpc45_default_icon  # noqa: E402

module_spec = importlib.util.spec_from_file_location(
    "remote_entity_localizations", ROOT / "scripts/sync_remote_entity_localizations.py"
)
generator = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(generator)


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


if __name__ == "__main__":
    unittest.main()
