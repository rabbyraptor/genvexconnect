"""DEV8.3: HA consumer keeps five baseline entities and 17 raw values."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from copy import deepcopy
import unittest

from test_snapshot import HERE  # Load the real import-free component namespace.
from dev_remote.raw_snapshot_v3 import validate_raw_v3
from dev_remote.snapshot import InvalidSnapshot
from test_freshness import load_coordinator, Reader

DEVICE = "123456789012"
BASE = {
    "supply_air": 6.8, "outdoor_air": 0.8,
    "exhaust_air": 2.2, "extract_air": 7.8,
    "humidity": 67.0,
}
RAW_BASE = {
    "supply_air": 368, "outdoor_air": 308,
    "exhaust_air": 322, "extract_air": 378,
    "humidity": 67,
}
RAW_EXTRA = {
    "frost_protection_temp": 0, "fan_duty_supply": 6000,
    "fan_duty_extract": 5800, "fan_rpm_supply": 2432,
    "fan_rpm_extract": 2268, "preheat_pwm": 0,
    "reheat_pwm": 0, "bypass_active_raw": 0,
    "bypass_analog_raw": 0, "alarm_word_1_raw": 0,
    "alarm_word_2_raw": 0, "rotor_rpm": 10,
}


def snapshot(optional=None):
    return {
        "schema_version": 3,
        "device_id": DEVICE,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "health": "ok",
        "values": dict(BASE),
        "raw_values": dict(RAW_BASE),
        "optional": {"raw_registers": dict(RAW_EXTRA if optional is None else optional)},
    }


class HASnapshotRawV3Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.Coordinator = load_coordinator()

    async def test_all_raw_registers_are_exposed_without_scaling(self):
        doc = snapshot()
        baseline, raw = validate_raw_v3(doc, expected_device_id=DEVICE)
        self.assertEqual(baseline, BASE)
        self.assertEqual(len(raw), 17)
        self.assertEqual(raw["fan_duty_supply"], 6000)
        self.assertEqual(raw["frost_protection_temp"], 0)
        self.assertEqual(raw["alarm_word_1_raw"], 0)
        self.assertIs(type(raw["alarm_word_2_raw"]), int)
        reader = Reader(doc)
        coord = self.Coordinator(None, DEVICE, reader, raw_registers_v3=True)
        values = await coord._async_update_data()
        self.assertEqual(len(values), 22)
        self.assertEqual(values["supply_air"], 6.8)
        self.assertEqual(values["raw_supply_air"], 368)
        self.assertEqual(values["raw_fan_duty_supply"], 6000)
        self.assertEqual(values["raw_rotor_rpm"], 10)

    async def test_secondary_rpc_failure_preserves_baseline_and_five_raws(self):
        doc = snapshot({})
        reader = Reader(doc)
        coord = self.Coordinator(None, DEVICE, reader, raw_registers_v3=True)
        values = await coord._async_update_data()
        self.assertEqual(len(values), 10)
        self.assertEqual(values["humidity"], 67.0)
        self.assertEqual(values["raw_humidity"], 67)
        self.assertNotIn("raw_fan_duty_supply", values)
        self.assertNotIn("raw_alarm_word_1_raw", values)

    async def test_new_missing_extras_are_not_retained_as_old_values(self):
        doc = snapshot()
        reader = Reader(doc)
        coord = self.Coordinator(None, DEVICE, reader, raw_registers_v3=True)
        self.assertIn("raw_rotor_rpm", await coord._async_update_data())
        reader.payload = snapshot({})
        self.assertNotIn("raw_rotor_rpm", await coord._async_update_data())
        self.assertEqual(coord._last_values["humidity"], 67.0)

    async def test_invalid_optional_is_not_accepted_as_normal_baseline(self):
        bad = snapshot()
        bad["optional"]["raw_registers"].pop("rotor_rpm")
        with self.assertRaises(InvalidSnapshot):
            validate_raw_v3(bad, expected_device_id=DEVICE)
        bad = snapshot()
        bad["raw_values"]["humidity"] = True
        with self.assertRaises(InvalidSnapshot):
            validate_raw_v3(bad, expected_device_id=DEVICE)
        bad = snapshot()
        bad["optional"]["raw_registers"]["fan_duty_supply"] = 32768
        with self.assertRaises(InvalidSnapshot):
            validate_raw_v3(bad, expected_device_id=DEVICE)

    async def test_wrong_device_and_stale_snapshots_rejected(self):
        with self.assertRaises(InvalidSnapshot):
            validate_raw_v3(snapshot(), expected_device_id="999999999999")
        doc = snapshot()
        doc["timestamp_utc"] = (
            datetime.now(timezone.utc) - timedelta(minutes=4)
        ).isoformat()
        with self.assertRaises(InvalidSnapshot):
            validate_raw_v3(doc, expected_device_id=DEVICE)


if __name__ == "__main__":
    unittest.main()
