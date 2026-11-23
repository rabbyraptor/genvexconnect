"""Offline tests for fresh, complete, private HA sensor snapshots."""
from datetime import datetime, timedelta, timezone
import unittest

from snapshot_contract import SnapshotError, parse_snapshot


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.snapshot = {
            "schema_version": 1, "device_id": "123456789012",
            "timestamp_utc": self.now.isoformat(), "health": "ok",
            "values": {
                "supply_air": 6.5, "outdoor_air": 0.1,
                "exhaust_air": 1.5, "extract_air": 7.6, "humidity": 66.0,
            },
        }

    def parse(self):
        return parse_snapshot(self.snapshot, expected_device_id="123456789012", now=self.now)

    def test_valid_live_snapshot(self):
        self.assertEqual(self.parse()["supply_air"], 6.5)

    def test_stale_snapshot_unavailable(self):
        self.snapshot["timestamp_utc"] = (self.now - timedelta(minutes=4)).isoformat()
        with self.assertRaises(SnapshotError):
            self.parse()

    def test_future_timestamp_unavailable(self):
        self.snapshot["timestamp_utc"] = (self.now + timedelta(minutes=2)).isoformat()
        with self.assertRaises(SnapshotError):
            self.parse()

    def test_incomplete_snapshot_unavailable(self):
        del self.snapshot["values"]["humidity"]
        with self.assertRaises(SnapshotError):
            self.parse()

    def test_wrong_device_unavailable(self):
        self.snapshot["device_id"] = "000000000000"
        with self.assertRaises(SnapshotError):
            self.parse()

    def test_offline_worker_unavailable(self):
        self.snapshot["health"] = "error"
        with self.assertRaises(SnapshotError):
            self.parse()

    def test_forged_credentials_field_rejected(self):
        self.snapshot["password"] = "not-for-HA"
        with self.assertRaises(SnapshotError):
            self.parse()

    def test_bad_numeric_values_rejected(self):
        for value in (True, "6.5", float("nan"), float("inf")):
            with self.subTest(value=value):
                self.snapshot["values"]["supply_air"] = value
                with self.assertRaises(SnapshotError):
                    self.parse()

    def test_schema_version_strict(self):
        self.snapshot["schema_version"] = True
        with self.assertRaises(SnapshotError):
            self.parse()

    def test_reject_naive_timestamp(self):
        self.snapshot["timestamp_utc"] = "2026-11-20T01:00:00"
        with self.assertRaises(SnapshotError):
            self.parse()


if __name__ == "__main__":
    unittest.main()
