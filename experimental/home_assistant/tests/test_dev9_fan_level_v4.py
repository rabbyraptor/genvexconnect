"""DEV9 v4 RPC42 fan-stage + RPC45 telemetry end-to-end offline contract.

No SDK, network, Home Assistant Core, device or credentials.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import sys
import unittest

from test_snapshot import HERE
from dev_remote.raw_snapshot_v4 import validate_v4
from dev_remote.snapshot import InvalidSnapshot

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / "genvex-nabto-remote/runtime"
sys.path.insert(0, str(APP))
try:
    from raw_registers_v3 import make_raw_v3
    from raw_snapshot_v4 import make_v4, parse_v4
    from persistent_rpc45_worker import SCHEMA, SCHEMA42, decode_fan_level
    from snapshot_api_v4 import V4_PATH, handle_v4_read_request
finally:
    sys.path.remove(str(APP))

DEVICE = "123456789012"
TOKEN = "T" * 43
SENSOR_RAW = (368, 308, 322, 378, 67)
OPTIONAL_RAW = (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)


def sample(level):
    v3 = make_raw_v3(
        device_id=DEVICE, measured_at=datetime.now(timezone.utc),
        baseline_raw=SENSOR_RAW, additional_raw=OPTIONAL_RAW,
    )
    return make_v4(v3, fan_level=level)


class FanLevelV4Tests(unittest.TestCase):
    def test_level_zero_is_not_missing_and_raw_registers_remain_exact(self):
        data = sample(0)
        app_scaled, app_raw, level = parse_v4(
            data, expected_device_id=DEVICE,
        )
        ha_scaled, ha_raw, ha_level = validate_v4(
            data, expected_device_id=DEVICE,
        )
        self.assertEqual(level, 0)
        self.assertEqual(ha_level, 0)
        self.assertEqual(ha_scaled, app_scaled)
        self.assertEqual(ha_raw, app_raw)
        for key in ("fan_duty_supply", "fan_duty_extract",
                    "fan_rpm_supply", "fan_rpm_extract"):
            self.assertEqual(ha_raw[key], 0)

    def test_null_stage_means_unavailable_not_zero(self):
        data = sample(None)
        self.assertIsNone(parse_v4(data, expected_device_id=DEVICE)[2])
        self.assertIsNone(validate_v4(data, expected_device_id=DEVICE)[2])
        self.assertEqual(data["optional"]["raw_registers"]["fan_duty_supply"], 0)

    def test_range_and_type_rejected_both_sides(self):
        for bad in (-1, 5, 65535, True, False, 1.0, "0", [], {}):
            with self.subTest(bad=bad):
                data = sample(0)
                data["fan_level"] = bad
                for parser in (parse_v4, validate_v4):
                    with self.assertRaises((ValueError, InvalidSnapshot)):
                        parser(data, expected_device_id=DEVICE)

    def test_v3_and_v4_shapes_distinct_and_raw_validation_retained(self):
        data = sample(2)
        self.assertEqual(data["schema_version"], 4)
        copy = dict(data)
        del copy["fan_level"]
        with self.assertRaises((ValueError, InvalidSnapshot)):
            validate_v4(copy, expected_device_id=DEVICE)
        data["optional"] = {"raw_registers": {"fan_duty_supply": 0}}
        with self.assertRaises(InvalidSnapshot):
            validate_v4(data, expected_device_id=DEVICE)

    def test_readonly_rpc_models_include_both_known_ids(self):
        combined = SCHEMA.replace(
            b"</unabto_queries>", b""
        ) + SCHEMA42.split(b"<unabto_queries>", 1)[1]
        self.assertIn(b'id="42"', combined)
        self.assertIn(b'id="45"', combined)
        self.assertNotIn(b'id="43"', combined)
        import xml.etree.ElementTree as ET
        parsed = ET.fromstring(combined)
        self.assertEqual({int(q.attrib["id"]) for q in parsed}, {42, 45})
        self.assertEqual(
            decode_fan_level('{"response":{"prefix_unknown":0,"values":[{"value":0}]}}'), 0
        )
        for content in (
            '{"response":{"values":[{"value":0}]}}',
            '{"response":{"prefix_unknown":0,"values":[{"value":5}]}}',
            '{"response":{"prefix_unknown":0,"values":[{"value":false}]}}',
            '{"response":{"prefix_unknown":0,"values":[]}}',
        ):
            self.assertIsNone(decode_fan_level(content))

    def test_internal_v4_endpoint_authorizes_before_snapshot(self):
        opts = dict(
            method="GET", path=V4_PATH,
            expected_token=TOKEN, device_id=DEVICE,
        )
        self.assertEqual(handle_v4_read_request(
            **opts, authorization="Bearer invalid", snapshot=sample(0))[0], 401)
        self.assertEqual(handle_v4_read_request(
            **opts, authorization="Bearer " + TOKEN, snapshot=None)[0], 503)
        status, body = handle_v4_read_request(
            **opts, authorization="Bearer " + TOKEN, snapshot=sample(0))
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["fan_level"], 0)
        self.assertEqual(handle_v4_read_request(
            **(opts | {"method": "POST"}), authorization="Bearer " + TOKEN,
            snapshot=sample(0))[0], 404)


if __name__ == "__main__":
    unittest.main()
