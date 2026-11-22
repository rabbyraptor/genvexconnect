"""DEV8.4.3 accelerated offline recovery/soak for the HA v3 coordinator.

Exercises hundreds of scheduled samples without waiting real minutes.
Device, network and Supervisor are fully synthetic.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from test_snapshot import HERE
from test_freshness import Reader, UpdateFailed, load_coordinator
from dev_remote.freshness import GRACE_SECONDS
from dev_remote.runtime_client import RuntimeUnavailable

DEVICE = "123456789012"
BASELINE = (368, 308, 322, 378, 67)
CANDIDATES = (
    0, 6000, 5800, 2432, 2268, 0, 0, 0, 0, 0, 0, 10,
)
BASE_KEYS = (
    "supply_air", "outdoor_air", "exhaust_air", "extract_air", "humidity",
)
EXTRA_KEYS = (
    "frost_protection_temp", "fan_duty_supply", "fan_duty_extract",
    "fan_rpm_supply", "fan_rpm_extract", "preheat_pwm", "reheat_pwm",
    "bypass_active_raw", "bypass_analog_raw", "alarm_word_1_raw",
    "alarm_word_2_raw", "rotor_rpm",
)


def snapshot(*, extra: bool = True, stamp: datetime | None = None):
    stamp = stamp or datetime.now(timezone.utc)
    return {
        "schema_version": 3,
        "device_id": DEVICE,
        "timestamp_utc": stamp.isoformat(),
        "health": "ok",
        "values": {
            "supply_air": 6.8, "outdoor_air": 0.8,
            "exhaust_air": 2.2, "extract_air": 7.8,
            "humidity": 67.0,
        },
        "raw_values": dict(zip(BASE_KEYS, BASELINE)),
        "optional": {
            "raw_registers": dict(zip(EXTRA_KEYS, CANDIDATES))
            if extra else {},
        },
    }


class AcceleratedRawSoakTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.reader = Reader(snapshot())
        self.coordinator = load_coordinator()(
            None, DEVICE, self.reader, raw_registers_v3=True,
        )

    async def test_360_serial_cycles_with_dropouts_and_optional_loss(self):
        last_good = None
        last_stamp = None
        fresh_cycles = 0
        failed_cycles = 0
        missing_cycles = 0
        for cycle in range(360):
            if cycle % 11 == 10:
                # Known transport failure: preserve validated last sample
                # until ten-minute grace expires.
                self.reader.payload = RuntimeUnavailable("simulated RPC outage")
                data = await self.coordinator._async_update_data()
                self.assertEqual(data, last_good)
                self.assertEqual(self.coordinator.last_sample_utc, last_stamp)
                failed_cycles += 1
                continue
            extra = cycle % 17 != 16
            self.reader.payload = snapshot(extra=extra)
            data = await self.coordinator._async_update_data()
            self.assertEqual(data["supply_air"], 6.8)
            self.assertEqual(data["raw_humidity"], 67)
            self.assertEqual(data["raw_supply_air"], 368)
            self.assertEqual(len(data), 22 if extra else 10)
            self.assertEqual("raw_fan_duty_supply" in data, extra)
            self.assertEqual("raw_alarm_word_1_raw" in data, extra)
            self.assertTrue(all(
                type(data["raw_" + key]) is int
                for key in BASE_KEYS
            ))
            last_good = data
            last_stamp = self.coordinator.last_sample_utc
            fresh_cycles += 1
            if not extra:
                missing_cycles += 1
        self.assertGreater(fresh_cycles, 320)
        self.assertGreater(failed_cycles, 25)
        self.assertGreater(missing_cycles, 10)

    async def test_grace_expiration_and_valid_snapshot_restores_17_raw(self):
        first = await self.coordinator._async_update_data()
        self.assertEqual(len(first), 22)
        self.coordinator.last_sample_utc -= timedelta(
            seconds=GRACE_SECONDS + 1,
        )
        self.reader.payload = RuntimeUnavailable("offline")
        with self.assertRaises(UpdateFailed):
            await self.coordinator._async_update_data()

        self.reader.payload = snapshot(extra=False)
        recovery = await self.coordinator._async_update_data()
        self.assertEqual(len(recovery), 10)
        self.assertNotIn("raw_rotor_rpm", recovery)

        self.reader.payload = snapshot(extra=True)
        expanded = await self.coordinator._async_update_data()
        self.assertEqual(len(expanded), 22)
        self.assertEqual(expanded["raw_rotor_rpm"], 10)


if __name__ == "__main__":
    unittest.main()
