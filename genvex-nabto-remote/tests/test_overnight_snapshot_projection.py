"""Offline regression for shared v1/v3 projection in DEV9 v3/v4 cache.

No Nabto SDK, network, Home Assistant Core, credentials, or live device.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

RUNTIME = Path(__file__).resolve().parents[1] / "runtime"
sys.path.insert(0, str(RUNTIME))

from raw_registers_v3 import BASE_KEYS, OPTIONAL_KEYS, make_raw_v3
from raw_snapshot_v4 import make_v4
from raw_snapshot_state_v3 import RawV3SnapshotState, _build_v1_v3_snapshots
from raw_snapshot_state_v4 import RawV4SnapshotState

DEVICE_ID = "123456789012"
BASE_RAW = (368, 308, 322, 378, 67)
EXTRA_RAW = (0, 6000, 5800, 2432, 2268, 0, 0, 0, 0, 0, 0, 10)


class StubPoller:
    device_id = DEVICE_ID

    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = 0

    async def poll_once(self):
        self.calls += 1
        return self.snapshot


class ProjectionTests(unittest.TestCase):
    def test_whitelist_and_no_aliasing_between_v1_v3(self):
        raw = {
            key: index for index, key in enumerate(BASE_KEYS + OPTIONAL_KEYS)
        }
        baseline = {"supply_air": 7.0, "humidity": 64.0}
        v1, v3 = _build_v1_v3_snapshots(
            device_id=DEVICE_ID,
            timestamp_utc="2026-11-23T00:00:00+00:00",
            baseline=baseline,
            raw=raw,
        )
        self.assertEqual(v1["schema_version"], 1)
        self.assertEqual(v3["schema_version"], 3)
        self.assertEqual(set(v1), {
            "schema_version", "device_id", "timestamp_utc", "health", "values"
        })
        self.assertEqual(set(v3["raw_values"]), set(BASE_KEYS))
        self.assertEqual(
            set(v3["optional"]["raw_registers"]), set(OPTIONAL_KEYS)
        )
        baseline["supply_air"] = -100
        raw[BASE_KEYS[0]] = -100
        v1["values"]["supply_air"] = -200
        self.assertEqual(v3["values"]["supply_air"], 7.0)
        self.assertEqual(v3["raw_values"][BASE_KEYS[0]], 0)


class VersionedCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_v4_and_v3_project_identical_legacy_and_raw_shapes(self):
        data = make_raw_v3(
            device_id=DEVICE_ID,
            measured_at=datetime.now(timezone.utc),
            baseline_raw=BASE_RAW,
            additional_raw=EXTRA_RAW,
        )
        old_poller = StubPoller(data)
        new_poller = StubPoller(make_v4(data, fan_level=2))
        old_state = RawV3SnapshotState(old_poller)
        new_state = RawV4SnapshotState(new_poller)
        self.assertTrue(await old_state.refresh())
        self.assertTrue(await new_state.refresh())
        self.assertEqual(old_poller.calls, 1)
        self.assertEqual(new_poller.calls, 1)
        self.assertEqual(old_state.current(), new_state.current())
        self.assertEqual(old_state.current_v3(), new_state.current_v3())
        self.assertEqual(new_state.current_v4()["fan_level"], 2)
        self.assertEqual(
            new_state.current_v4()["optional"]["raw_registers"],
            old_state.current_v3()["optional"]["raw_registers"],
        )
        detached = new_state.current_v3()
        detached["values"]["supply_air"] = -99
        detached["raw_values"][BASE_KEYS[0]] = -99
        self.assertEqual(
            new_state.current_v4()["values"]["supply_air"],
            old_state.current()["values"]["supply_air"],
        )

    async def test_optional_raw_absent_and_null_stage_remain_distinct(self):
        data = make_raw_v3(
            device_id=DEVICE_ID,
            measured_at=datetime.now(timezone.utc),
            baseline_raw=BASE_RAW,
            additional_raw=None,
        )
        old_state = RawV3SnapshotState(StubPoller(data))
        new_state = RawV4SnapshotState(StubPoller(make_v4(data, fan_level=None)))
        self.assertTrue(await old_state.refresh())
        self.assertTrue(await new_state.refresh())
        self.assertEqual(old_state.current_v3(), new_state.current_v3())
        self.assertEqual(new_state.current_v4()["optional"]["raw_registers"], {})
        self.assertIsNone(new_state.current_v4()["fan_level"])
        self.assertIsNotNone(new_state.current())


if __name__ == "__main__":
    unittest.main()
