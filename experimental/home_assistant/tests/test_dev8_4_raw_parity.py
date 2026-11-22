"""DEV8.4.2 raw register parity from source to HA, including full int16 range.

All inputs are synthetic. No SDK, App, gateway or HAOS process is started.
"""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import random
import sys
import unittest

from test_snapshot import HERE
from dev_remote.const import RAW_REGISTERS, SENSORS
from dev_remote.raw_snapshot_v3 import validate_raw_v3

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "experimental" / "genvex_remote"
APP = ROOT / "genvex-nabto-remote" / "runtime"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(APP))
from raw_registers_v3 import (
    ALL_REGISTERS, BASE_KEYS, OPTIONAL_KEYS, make_raw_v3,
    parse_raw_v3,
)
from dev8_register_evidence import inventory, OBSERVED_CANDIDATE_RAW


class RawRegisterParityTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.device = "123456789012"

    def test_17_addresses_and_names_match_at_all_three_boundaries(self):
        backend = tuple((row.key, row.address) for row in inventory())
        app = ALL_REGISTERS
        homeassistant = tuple((row.key, row.address) for row in RAW_REGISTERS)
        self.assertEqual(app, backend)
        self.assertEqual(app, homeassistant)
        self.assertEqual(len(app), 17)
        self.assertEqual(tuple(x.key for x in SENSORS), BASE_KEYS)
        self.assertEqual(
            tuple(raw for _, raw in app[5:]),
            (24, 18, 19, 35, 36, 41, 42, 53, 40, 114, 115, 50),
        )

    def test_archived_twelve_raw_values_are_identical_in_ha_snapshot(self):
        doc = make_raw_v3(
            device_id=self.device, measured_at=self.now,
            baseline_raw=(368, 308, 322, 378, 67),
            additional_raw=OBSERVED_CANDIDATE_RAW,
        )
        app_scaled, app_raw = parse_raw_v3(
            doc, expected_device_id=self.device, now=self.now,
        )
        ha_scaled, ha_raw = validate_raw_v3(
            doc, expected_device_id=self.device, now=self.now,
        )
        self.assertEqual(app_scaled, ha_scaled)
        self.assertEqual(app_raw, ha_raw)
        self.assertEqual(
            tuple(ha_raw[key] for key in OPTIONAL_KEYS), OBSERVED_CANDIDATE_RAW,
        )
        self.assertEqual(ha_raw["frost_protection_temp"], 0)
        self.assertEqual(ha_raw["fan_duty_supply"], 6000)
        self.assertEqual(ha_raw["alarm_word_2_raw"], 0)

    def test_round_trip_random_signed_int16_is_exact(self):
        rng = random.Random(8402)
        baseline = (367, 311, 322, 380, 66)
        for _ in range(200):
            extras = tuple(rng.randint(-32768, 32767) for _ in OPTIONAL_KEYS)
            doc = make_raw_v3(
                device_id=self.device, measured_at=self.now,
                baseline_raw=baseline, additional_raw=extras,
            )
            backend_scaled, backend_raw = parse_raw_v3(
                doc, expected_device_id=self.device, now=self.now,
            )
            ha_scaled, ha_raw = validate_raw_v3(
                doc, expected_device_id=self.device, now=self.now,
            )
            self.assertEqual(ha_scaled, backend_scaled)
            self.assertEqual(ha_raw, backend_raw)
            self.assertEqual(
                tuple(ha_raw[key] for key in OPTIONAL_KEYS), extras,
            )
            self.assertTrue(all(type(v) is int for v in ha_raw.values()))

    def test_optional_read_absent_never_masquerades_as_raw_zero(self):
        doc = make_raw_v3(
            device_id=self.device, measured_at=self.now,
            baseline_raw=(368, 308, 322, 378, 67),
            additional_raw=None,
        )
        for parser in (parse_raw_v3, validate_raw_v3):
            _, data = parser(
                doc, expected_device_id=self.device, now=self.now,
            )
            self.assertEqual(tuple(data), BASE_KEYS)
            self.assertNotIn("fan_duty_supply", data)
            self.assertNotIn("alarm_word_1_raw", data)
            self.assertNotIn("rotor_rpm", data)


if __name__ == "__main__":
    unittest.main()
