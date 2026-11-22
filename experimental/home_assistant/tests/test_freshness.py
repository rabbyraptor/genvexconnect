"""Offline tests for age-based recovery and coordinator availability policy."""
import asyncio
from datetime import datetime, timedelta, timezone
import importlib.util
import sys
import types
import unittest

from test_snapshot import HERE
from dev_remote.freshness import GRACE_SECONDS, age_seconds, within_grace


class CoordinatorBase:
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, *args, **kwargs):
        self.data = None
        self.init_kwargs = kwargs


class UpdateFailed(Exception):
    pass


def load_coordinator():
    ha = types.ModuleType("homeassistant")
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = type("HomeAssistant", (), {})
    helpers = types.ModuleType("homeassistant.helpers")
    update = types.ModuleType("homeassistant.helpers.update_coordinator")
    update.DataUpdateCoordinator = CoordinatorBase
    update.UpdateFailed = UpdateFailed
    sys.modules.update({
        "homeassistant": ha,
        "homeassistant.core": core,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.update_coordinator": update,
    })
    spec = importlib.util.spec_from_file_location(
        "dev_remote.coordinator", HERE / "coordinator.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.GenvexRemoteCoordinator


class Reader:
    def __init__(self, payload):
        self.payload = payload

    async def async_fetch_snapshot(self, device_id):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FreshnessTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.Coordinator = load_coordinator()
        self.now = datetime.now(timezone.utc)
        self.payload = {
            "schema_version": 1,
            "device_id": "123456789012",
            "timestamp_utc": self.now.isoformat(),
            "health": "ok",
            "values": {
                "supply_air": 7.6, "outdoor_air": 4.0,
                "exhaust_air": 4.6, "extract_air": 7.8,
                "humidity": 67.0,
            },
        }
        self.reader = Reader(self.payload)
        self.coordinator = self.Coordinator(None, "123456789012", self.reader)

    async def test_installed_ha_passes_config_entry_keyword(self):
        entry = object()
        coordinator = self.Coordinator(
            None, "123456789012", self.reader, config_entry=entry
        )
        self.assertIs(coordinator.init_kwargs["config_entry"], entry)

    async def test_short_outage_preserves_values_and_original_measurement(self):
        original = await self.coordinator._async_update_data()
        original_time = self.coordinator.last_sample_utc
        from dev_remote.runtime_client import RuntimeUnavailable
        self.reader.payload = RuntimeUnavailable("network down")
        cached = await self.coordinator._async_update_data()
        self.assertEqual(cached, original)
        self.assertEqual(original_time, self.coordinator.last_sample_utc)

    async def test_repeated_cached_snapshot_does_not_refresh_age(self):
        await self.coordinator._async_update_data()
        measured = self.coordinator.last_sample_utc
        await self.coordinator._async_update_data()
        self.assertEqual(measured, self.coordinator.last_sample_utc)

    async def test_outage_after_ten_minutes_marks_unavailable(self):
        await self.coordinator._async_update_data()
        self.coordinator.last_sample_utc -= timedelta(seconds=GRACE_SECONDS + 1)
        from dev_remote.runtime_client import RuntimeUnavailable
        self.reader.payload = RuntimeUnavailable("offline")
        with self.assertRaises(UpdateFailed):
            await self.coordinator._async_update_data()

    async def test_recovery_accepts_new_measurement(self):
        await self.coordinator._async_update_data()
        self.coordinator.last_sample_utc -= timedelta(seconds=GRACE_SECONDS + 1)
        self.payload["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
        self.payload["values"]["humidity"] = 66.0
        recovered = await self.coordinator._async_update_data()
        self.assertEqual(recovered["humidity"], 66.0)
        self.assertTrue(within_grace(self.coordinator.last_sample_utc))

    async def test_no_initial_measurement_fails_closed(self):
        from dev_remote.runtime_client import RuntimeUnavailable
        self.reader.payload = RuntimeUnavailable("offline")
        with self.assertRaises(UpdateFailed):
            await self.coordinator._async_update_data()

    async def test_age_based_on_measurement(self):
        stamp = self.now - timedelta(seconds=240)
        self.assertAlmostEqual(age_seconds(stamp, now=self.now), 240)
        self.assertTrue(within_grace(stamp, now=self.now))
        self.assertFalse(within_grace(self.now - timedelta(seconds=601), now=self.now))


if __name__ == "__main__":
    unittest.main()
