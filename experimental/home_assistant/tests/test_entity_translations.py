"""Guard shipped Home Assistant custom integration entity translations."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "genvex_remote"
EXPECTED_KEYS = {
    "supply_air", "outdoor_air", "exhaust_air", "extract_air", "humidity"
}


class EntityTranslationsTest(unittest.TestCase):
    def test_english_fallback_shipped_and_complete(self):
        source = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
        shipped = json.loads(
            (COMPONENT / "translations" / "en.json").read_text(encoding="utf-8")
        )
        self.assertEqual(shipped, source)
        names = shipped["entity"]["sensor"]
        self.assertEqual(set(names), EXPECTED_KEYS)
        self.assertTrue(all(isinstance(v["name"], str) and v["name"] for v in names.values()))

    def test_danish_names_match_english_keys(self):
        english = json.loads(
            (COMPONENT / "translations" / "en.json").read_text(encoding="utf-8")
        )
        danish = json.loads(
            (COMPONENT / "translations" / "da.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            set(danish["entity"]["sensor"]),
            set(english["entity"]["sensor"]),
        )
        self.assertEqual(
            {k: v["name"] for k, v in danish["entity"]["sensor"].items()},
            {
                "supply_air": "Indblæsning",
                "outdoor_air": "Udeluft",
                "exhaust_air": "Afkast",
                "extract_air": "Udsugning",
                "humidity": "Luftfugtighed",
            },
        )


if __name__ == "__main__":
    unittest.main()
