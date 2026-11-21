"""Offline coordinator lifecycle contract; Home Assistant Core is not required.

Exercise the real GenvexRemoteCoordinator logic with only minimal HA API stubs.
No network access, SDK credentials, or Home Assistant startup.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "genvex_remote"
PKG = "dev3_remote_contract"

pkg = types.ModuleType(PKG)
pkg.__path__ = [str(COMPONENT)]
sys.modules[PKG] = pkg

for name in ("const", "runtime_client", "snapshot"):
    spec = importlib.util.spec_from_file_location(f"{PKG}.{name}", COMPONENT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

# Coordinator uses only these Home Assistant interfaces. Stub behavior is
# intentionally limited: tests call _async_update_data directly.
ha = types.ModuleType("homeassistant")
ha.__path__ = []
core = types.ModuleType("homeassistant.core")
core.HomeAssistant = type("HomeAssistant", (), {})
config_entries = types.ModuleType("homeassistant.config_entries")
config_entries.ConfigEntry = type("ConfigEntry", (), {})
sys.modules["homeassistant.config_entries"] = config_entries
helpers = types.ModuleType("homeassistant.helpers")
helpers.__path__ = []
update = types.ModuleType("homeassistant.helpers.update_coordinator")


class FakeDataUpdateCoordinator:
    def __class_getitem__(cls, _):
        return cls

    def __init__(self, hass, *, logger, name, update_interval, config_entry=None):
        self.hass = hass
        self.name = name
        self.update_interval = update_interval
        self.config_entry = config_entry


class FakeUpdateFailed(Exception):
    pass


update.DataUpdateCoordinator = FakeDataUpdateCoordinator
update.UpdateFailed = FakeUpdateFailed
sys.modules["homeassistant"] = ha
sys.modules["homeassistant.core"] = core
sys.modules["homeassistant.helpers"] = helpers
sys.modules["homeassistant.helpers.update_coordinator"] = update
spec = importlib.util.spec_from_file_location(
    f"{PKG}.coordinator", COMPONENT / "coordinator.py"
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

Coordinator = module.GenvexRemoteCoordinator
from dev3_remote_contract.runtime_client import RuntimeUnavailable

DEVICE_ID = "123456789012"
VALUES = {
    "supply_air": 6.7, "outdoor_air": 0.2,
    "exhaust_air": 1.8, "extract_air": 7.8, "humidity": 66.0,
}


def snapshot(*, age_seconds=0, device_id=DEVICE_ID, values=None):
    return {
        "schema_version": 1, "device_id": device_id,
        "timestamp_utc": (
            datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
        ).isoformat(),
        "health": "ok",
        "values": dict(VALUES if values is None else values),
    }


class CoordinatorContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_five_values(self):
        reader = types.SimpleNamespace(async_fetch_snapshot=AsyncMock(return_value=snapshot()))
        coordinator = Coordinator(core.HomeAssistant(), DEVICE_ID, reader)
        values = await coordinator._async_update_data()
        self.assertEqual(values, VALUES)
        self.assertEqual(coordinator.update_interval.total_seconds(), 60)
        reader.async_fetch_snapshot.assert_awaited_once_with(DEVICE_ID)

    async def test_runtime_unavailable_marks_failure(self):
        reader = types.SimpleNamespace(
            async_fetch_snapshot=AsyncMock(side_effect=RuntimeUnavailable("sensitive"))
        )
        coordinator = Coordinator(core.HomeAssistant(), DEVICE_ID, reader)
        with self.assertRaises(FakeUpdateFailed) as caught:
            await coordinator._async_update_data()
        self.assertEqual(str(caught.exception),
                         "Genvex remote readings are unavailable")
        self.assertNotIn("sensitive", str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)

    async def test_stale_snapshot_rejected(self):
        reader = types.SimpleNamespace(
            async_fetch_snapshot=AsyncMock(return_value=snapshot(age_seconds=200))
        )
        with self.assertRaises(FakeUpdateFailed):
            await Coordinator(core.HomeAssistant(), DEVICE_ID, reader)._async_update_data()

    async def test_wrong_device_rejected(self):
        reader = types.SimpleNamespace(
            async_fetch_snapshot=AsyncMock(return_value=snapshot(device_id="000000000000"))
        )
        with self.assertRaises(FakeUpdateFailed):
            await Coordinator(core.HomeAssistant(), DEVICE_ID, reader)._async_update_data()

    async def test_incomplete_readings_rejected(self):
        readings = dict(VALUES)
        del readings["humidity"]
        reader = types.SimpleNamespace(
            async_fetch_snapshot=AsyncMock(return_value=snapshot(values=readings))
        )
        with self.assertRaises(FakeUpdateFailed):
            await Coordinator(core.HomeAssistant(), DEVICE_ID, reader)._async_update_data()

    async def test_recovery_after_failed_fetch(self):
        reader = types.SimpleNamespace(async_fetch_snapshot=AsyncMock(
            side_effect=[RuntimeUnavailable("offline"), snapshot()]
        ))
        coordinator = Coordinator(core.HomeAssistant(), DEVICE_ID, reader)
        with self.assertRaises(FakeUpdateFailed):
            await coordinator._async_update_data()
        self.assertEqual(await coordinator._async_update_data(), VALUES)
        self.assertEqual(reader.async_fetch_snapshot.await_count, 2)


if __name__ == "__main__":
    unittest.main()
