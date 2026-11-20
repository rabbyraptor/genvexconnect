"""Offline contract tests for an additive, inert snapshot v2 draft."""
from datetime import datetime, timedelta, timezone
import unittest

from snapshot_contract import SnapshotError, parse_snapshot
from snapshot_v2_draft import decode_optional_fan_duty, make_v2_from_v1, parse_v2


class V2DraftTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
        self.v1 = {
            "schema_version": 1, "device_id": "123456789012",
            "timestamp_utc": self.now.isoformat(), "health": "ok",
            "values": {"supply_air": 6.7, "outdoor_air": 0.4,
                       "exhaust_air": 1.8, "extract_air": 7.8, "humidity": 67.0},
        }

    def test_fan_scale_matches_observed_batch(self):
        self.assertEqual(decode_optional_fan_duty((6000, 5800)),
                         {"fan_duty_supply": 60.0, "fan_duty_extract": 58.0})

    def test_v2_additive_and_v1_unchanged(self):
        v2 = make_v2_from_v1(self.v1, expected_device_id="123456789012",
                             fan_raw=(6000, 5800), now=self.now)
        baseline, fans = parse_v2(v2, expected_device_id="123456789012", now=self.now)
        self.assertEqual(baseline, parse_snapshot(self.v1, expected_device_id="123456789012", now=self.now))
        self.assertEqual(fans, {"fan_duty_supply": 60.0, "fan_duty_extract": 58.0})
        self.assertEqual(self.v1["schema_version"], 1)
        with self.assertRaises(SnapshotError):
            parse_snapshot(v2, expected_device_id="123456789012", now=self.now)

    def test_optional_failure_never_destroys_baseline(self):
        for raw in (None, (6000,), (6000, 5800, 1), (True, 5800),
                    (6000, "5800"), (10001, 5800), (-1, 5800)):
            with self.subTest(raw=raw):
                v2 = make_v2_from_v1(self.v1, expected_device_id="123456789012",
                                     fan_raw=raw, now=self.now)
                baseline, fans = parse_v2(v2, expected_device_id="123456789012", now=self.now)
                self.assertEqual(fans, {})
                self.assertEqual(baseline["humidity"], 67.0)

    def test_bad_baseline_still_fails(self):
        self.v1["timestamp_utc"] = (self.now - timedelta(minutes=5)).isoformat()
        with self.assertRaises(SnapshotError):
            make_v2_from_v1(self.v1, expected_device_id="123456789012",
                            fan_raw=(6000, 5800), now=self.now)

    def test_wrong_device_and_bad_optional_fail(self):
        v2 = make_v2_from_v1(self.v1, expected_device_id="123456789012", now=self.now)
        with self.assertRaises(SnapshotError):
            parse_v2(v2, expected_device_id="999999999999", now=self.now)
        for bad in ({"fan_duty_supply": 60}, {"fan_duty_supply": True, "fan_duty_extract": 58},
                    {"fan_duty_supply": 101, "fan_duty_extract": 58}):
            with self.subTest(bad=bad):
                v2["optional"]["fan_duty"] = bad
                with self.assertRaises(SnapshotError):
                    parse_v2(v2, expected_device_id="123456789012", now=self.now)

    def test_no_sdk_or_network_imports(self):
        from pathlib import Path
        source = (Path(__file__).with_name("snapshot_v2_draft.py")).read_text()
        self.assertNotIn("import nabto", source.lower())
        self.assertNotIn("socket", source.lower())
        self.assertNotIn("requests", source.lower())


if __name__ == "__main__":
    unittest.main()
