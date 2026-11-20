"""Plain Python HA-side v2 contract parity tests, no HA Core or network."""
from datetime import datetime, timedelta, timezone
import importlib.util
import unittest

# Use test_snapshot's no-HA package loader to preserve existing v1 imports.
import test_snapshot  # noqa: F401
from dev_remote.snapshot import InvalidSnapshot, validate_snapshot

from pathlib import Path
import sys

PATH = Path(__file__).resolve().parents[1] / "custom_components" / "genvex_remote" / "snapshot_v2_draft.py"
spec = importlib.util.spec_from_file_location("dev_remote.snapshot_v2_draft", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
validate_v2_snapshot = module.validate_v2_snapshot


class HACandidateV2Tests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 20, 16, tzinfo=timezone.utc)
        self.payload = {
            "schema_version": 2, "device_id": "123456789012",
            "timestamp_utc": self.now.isoformat(), "health": "ok",
            "values": {"supply_air": 6.7, "outdoor_air": 0.4,
                       "exhaust_air": 1.8, "extract_air": 7.8,
                       "humidity": 67.0},
            "optional": {"fan_duty": {
                "fan_duty_supply": 60.0, "fan_duty_extract": 58.0,
            }},
        }

    def check(self):
        return validate_v2_snapshot(
            self.payload, expected_device_id="123456789012", now=self.now
        )

    def test_exact_five_baseline_and_two_optionals(self):
        base, fans = self.check()
        self.assertEqual(base["humidity"], 67.0)
        self.assertEqual(fans, {"fan_duty_supply": 60.0, "fan_duty_extract": 58.0})
        self.assertEqual(set(base), {
            "supply_air", "outdoor_air", "exhaust_air", "extract_air", "humidity"
        })
        with self.assertRaises(InvalidSnapshot):
            validate_snapshot(
                self.payload, expected_device_id="123456789012", now=self.now
            )

    def test_optional_empty_not_fabricated_zero(self):
        self.payload["optional"]["fan_duty"] = {}
        base, fans = self.check()
        self.assertEqual(base["supply_air"], 6.7)
        self.assertEqual(fans, {})

    def test_valid_real_zero(self):
        self.payload["optional"]["fan_duty"] = {
            "fan_duty_supply": 0, "fan_duty_extract": 0
        }
        _, fans = self.check()
        self.assertEqual(fans, {"fan_duty_supply": 0.0, "fan_duty_extract": 0.0})

    def test_partial_wrong_type_or_bad_percentage_fails(self):
        invalid = (
            {"fan_duty_supply": 60},
            {"fan_duty_supply": True, "fan_duty_extract": 58},
            {"fan_duty_supply": 101, "fan_duty_extract": 58},
            {"fan_duty_supply": float("nan"), "fan_duty_extract": 58},
            {"fan_duty_supply": "60", "fan_duty_extract": 58},
        )
        for fans in invalid:
            with self.subTest(fans=fans):
                self.payload["optional"]["fan_duty"] = fans
                with self.assertRaises(InvalidSnapshot):
                    self.check()

    def test_wrong_device_stale_and_unexpected_field_fails(self):
        with self.assertRaises(InvalidSnapshot):
            validate_v2_snapshot(
                self.payload, expected_device_id="000000000000", now=self.now
            )
        self.payload["timestamp_utc"] = (
            self.now - timedelta(minutes=4)
        ).isoformat()
        with self.assertRaises(InvalidSnapshot):
            self.check()
        self.payload["timestamp_utc"] = self.now.isoformat()
        self.payload["secret"] = "NOT_FOR_HA"
        with self.assertRaises(InvalidSnapshot):
            self.check()

    def test_baseline_missing_or_bad_fails_even_if_fans_good(self):
        del self.payload["values"]["humidity"]
        with self.assertRaises(InvalidSnapshot):
            self.check()


if __name__ == "__main__":
    unittest.main()
