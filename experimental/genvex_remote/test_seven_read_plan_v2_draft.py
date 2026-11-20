"""Offline checks for the fixed combined v2 seven-item read-only plan."""
from datetime import datetime, timezone
import unittest

from seven_read_plan_v2_draft import (
    ORDERED_ADDRESSES, ORDERED_KEYS, RPC_ID,
    decode_seven_to_v2, request_body,
)
from snapshot_contract import SnapshotError
from snapshot_v2_draft import parse_v2


class SevenReadPlanTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 20, 14, tzinfo=timezone.utc)
        self.raw = (367, 304, 318, 378, 67, 6000, 5800)
        self.device = "123456789012"

    def test_exact_order_and_read_only_request(self):
        self.assertEqual(RPC_ID, 45)
        self.assertEqual(ORDERED_ADDRESSES, (20, 21, 22, 23, 26, 18, 19))
        self.assertEqual(ORDERED_KEYS, (
            "supply_air", "outdoor_air", "exhaust_air",
            "extract_air", "humidity", "fan_duty_supply", "fan_duty_extract",
        ))
        self.assertEqual(request_body(), {
            "request": {
                "datapoints": [{"obj": 0, "address": a} for a in ORDERED_ADDRESSES],
                "trailer": 1,
            }
        })

    def test_one_timestamp_and_all_seven_values(self):
        payload = decode_seven_to_v2(
            self.raw, device_id=self.device, measured_at=self.now
        )
        baseline, fans = parse_v2(
            payload, expected_device_id=self.device, now=self.now
        )
        self.assertEqual(payload["timestamp_utc"], self.now.isoformat())
        self.assertEqual(baseline, {
            "supply_air": 6.7, "outdoor_air": 0.4,
            "exhaust_air": 1.8, "extract_air": 7.8, "humidity": 67.0,
        })
        self.assertEqual(fans, {
            "fan_duty_supply": 60.0, "fan_duty_extract": 58.0,
        })

    def test_invalid_optional_pair_is_unavailable_not_zero(self):
        p = decode_seven_to_v2(
            self.raw[:5] + (15000, 5800),
            device_id=self.device, measured_at=self.now,
        )
        self.assertEqual(p["optional"]["fan_duty"], {})
        self.assertEqual(p["values"]["humidity"], 67.0)

    def test_valid_zero_is_measurement(self):
        p = decode_seven_to_v2(
            self.raw[:5] + (0, 0),
            device_id=self.device, measured_at=self.now,
        )
        self.assertEqual(p["optional"]["fan_duty"], {
            "fan_duty_supply": 0.0, "fan_duty_extract": 0.0,
        })

    def test_fail_closed_on_any_missing_invalid_or_extra_value(self):
        for bad in (
            self.raw[:-1], self.raw + (1,),
            list(self.raw[:3]) + ["367"] + list(self.raw[4:]),
            list(self.raw[:3]) + [True] + list(self.raw[4:]),
            self.raw[:3] + (32768,) + self.raw[4:],
            None,
        ):
            with self.subTest(bad=bad), self.assertRaises(SnapshotError):
                decode_seven_to_v2(bad, device_id=self.device, measured_at=self.now)

    def test_device_and_timestamp_restrictions(self):
        for device, measured in (
            ("1234", self.now),
            (self.device, datetime(2026, 11, 20, 14)),
        ):
            with self.subTest(device=device, time=measured), self.assertRaises(
                (SnapshotError, ValueError)
            ):
                decode_seven_to_v2(
                    self.raw, device_id=device, measured_at=measured
                )

    def test_no_live_sdk_or_http_calls(self):
        from pathlib import Path
        source = Path(__file__).with_name("seven_read_plan_v2_draft.py").read_text()
        self.assertNotIn("nabtoRpcInvoke", source)
        self.assertNotIn("import requests", source)
        self.assertNotIn("create_subprocess", source)


if __name__ == "__main__":
    unittest.main()
