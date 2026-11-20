"""No-HA-Core, no-SDK tests for the proposed v2 Home Assistant view."""
from datetime import datetime, timedelta, timezone
import unittest

from ha_v2_projection import project_v2_sensors
from snapshot_contract import SnapshotError
from snapshot_v2_draft import make_v2_from_v1


class HAV2ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
        self.base = {
            "schema_version": 1, "device_id": "123456789012",
            "timestamp_utc": self.now.isoformat(), "health": "ok",
            "values": {
                "supply_air": 6.7, "outdoor_air": 0.4,
                "exhaust_air": 1.8, "extract_air": 7.8,
                "humidity": 67.0,
            },
        }

    def project(self, raw):
        snapshot = make_v2_from_v1(
            self.base, expected_device_id="123456789012",
            fan_raw=raw, now=self.now,
        )
        return project_v2_sensors(
            snapshot, expected_device_id="123456789012", now=self.now
        )

    def test_7_stable_sensor_keys_and_correct_values(self):
        rows = self.project((6000, 5800))
        self.assertEqual(len(rows), 7)
        self.assertEqual(
            [x.key for x in rows],
            ["supply_air", "outdoor_air", "exhaust_air", "extract_air",
             "humidity", "fan_duty_supply", "fan_duty_extract"],
        )
        self.assertEqual(
            [x.unique_id("123456789012") for x in rows[:5]],
            [f"123456789012_{key}" for key in (
                "supply_air", "outdoor_air", "exhaust_air", "extract_air", "humidity"
            )],
        )
        self.assertEqual([x.value for x in rows[5:]], [60.0, 58.0])
        self.assertTrue(all(x.available for x in rows))
        self.assertEqual([x.unit for x in rows[5:]], ["%", "%"])
        self.assertTrue(all(x.state_class == "measurement" for x in rows))
        self.assertEqual(rows[4].device_class, "humidity")

    def test_optional_failure_is_unavailable_not_zero(self):
        for raw in (None, (6000,), ("6000", 5800), (-1, 5800)):
            with self.subTest(raw=raw):
                rows = self.project(raw)
                self.assertTrue(all(x.available for x in rows[:5]))
                self.assertFalse(any(x.available for x in rows[5:]))
                self.assertEqual([x.value for x in rows[5:]], [None, None])
                self.assertEqual(rows[0].value, 6.7)

    def test_valid_zero_is_distinct_from_unavailable(self):
        rows = self.project((0, 0))
        self.assertTrue(all(x.available for x in rows[5:]))
        self.assertEqual([x.value for x in rows[5:]], [0.0, 0.0])

    def test_wrong_device_stale_and_missing_baseline_fail(self):
        snapshot = make_v2_from_v1(
            self.base, expected_device_id="123456789012",
            fan_raw=(6000, 5800), now=self.now,
        )
        with self.assertRaises(SnapshotError):
            project_v2_sensors(snapshot, expected_device_id="999999999999", now=self.now)
        with self.assertRaises(SnapshotError):
            project_v2_sensors(snapshot, expected_device_id="123456789012",
                               now=self.now + timedelta(minutes=4))
        del snapshot["values"]["humidity"]
        with self.assertRaises(SnapshotError):
            project_v2_sensors(snapshot, expected_device_id="123456789012", now=self.now)

    def test_no_rpm_alarm_or_control_entities(self):
        self.assertTrue(set(x.key for x in self.project((6000, 5800))).isdisjoint(
            {"fan_rpm_supply", "fan_rpm_extract", "preheat_pwm", "reheat_pwm",
             "rotor_rpm", "alarm_word_1_raw", "alarm_word_2_raw",
             "bypass_active_raw", "bypass_analog_raw", "frost_protection_temp"}
        ))


if __name__ == "__main__":
    unittest.main()
