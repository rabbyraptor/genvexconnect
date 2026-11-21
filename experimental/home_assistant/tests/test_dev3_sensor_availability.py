"""Offline five-sensor Home Assistant availability lifecycle contract.

Imports the actual remote coordinator and entity code with minimal HA stubs.
No HA Core, network, SDK, secrets or Home Assistant instance is started.
The coordinator stub models DataUpdateCoordinator's last_update_success
behavior; this does not replace an actual HA Core integration test.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock

# Reuse the existing offline harness's coordinator and HA stubs.
import test_dev3_coordinator as harness

PKG = harness.PKG
COMPONENT = harness.COMPONENT
Coordinator = harness.Coordinator
DEVICE_ID = harness.DEVICE_ID
VALUES = harness.VALUES
snapshot = harness.snapshot
RuntimeUnavailable = harness.RuntimeUnavailable
UpdateFailed = harness.FakeUpdateFailed

# Home Assistant API symbols used by the actual sensor module.
sensor = types.ModuleType("homeassistant.components.sensor")
sensor.SensorDeviceClass = types.SimpleNamespace(TEMPERATURE="temperature",
                                                HUMIDITY="humidity")
sensor.SensorStateClass = types.SimpleNamespace(MEASUREMENT="measurement")
sensor.SensorEntity = type("SensorEntity", (), {})

components = types.ModuleType("homeassistant.components")
components.__path__ = []
sys.modules["homeassistant.components"] = components
sys.modules["homeassistant.components.sensor"] = sensor

const = types.ModuleType("homeassistant.const")
const.UnitOfTemperature = types.SimpleNamespace(CELSIUS="°C")
const.PERCENTAGE = "%"
sys.modules["homeassistant.const"] = const

registry = types.ModuleType("homeassistant.helpers.device_registry")
registry.DeviceInfo = dict
sys.modules["homeassistant.helpers.device_registry"] = registry


class OfflineCoordinatorEntity:
    """Only availability behavior of HA's CoordinatorEntity is simulated."""

    def __init__(self, coordinator):
        self.coordinator = coordinator

    @property
    def available(self):
        return self.coordinator.last_update_success


harness.update.CoordinatorEntity = OfflineCoordinatorEntity
spec = importlib.util.spec_from_file_location(
    f"{PKG}.sensor", COMPONENT / "sensor.py"
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

from dev3_remote_contract.const import SENSORS

GenvexRemoteSensor = module.GenvexRemoteSensor


class SensorAvailabilityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.reader = types.SimpleNamespace(async_fetch_snapshot=AsyncMock())
        self.coordinator = Coordinator(
            harness.core.HomeAssistant(), DEVICE_ID, self.reader
        )
        self.coordinator.data = None
        self.coordinator.last_update_success = False
        self.entities = [
            GenvexRemoteSensor(self.coordinator, item) for item in SENSORS
        ]
        self.assertEqual(len(self.entities), 5)

    async def refresh(self):
        try:
            values = await self.coordinator._async_update_data()
        except UpdateFailed:
            # Mirrors the HA DataUpdateCoordinator failure flag without
            # discarding its previously stored data.
            self.coordinator.last_update_success = False
            return False
        else:
            self.coordinator.data = values
            self.coordinator.last_update_success = True
            return True

    async def test_failed_session_does_not_publish_old_readings_as_available(self):
        self.reader.async_fetch_snapshot.side_effect = [
            snapshot(), RuntimeUnavailable("SDK_SESSION_FAILED")
        ]
        self.assertTrue(await self.refresh())
        self.assertTrue(all(entity.available for entity in self.entities))
        self.assertEqual(
            {entity._key: entity.native_value for entity in self.entities},
            VALUES
        )

        self.assertFalse(await self.refresh())
        # Coordinator may retain data for debugging: entities must still
        # become unavailable through CoordinatorEntity's state flag.
        self.assertEqual(self.coordinator.data, VALUES)
        self.assertTrue(all(not entity.available for entity in self.entities))
        self.assertEqual(self.reader.async_fetch_snapshot.await_count, 2)

    async def test_atomic_recovery_restores_all_five_entities(self):
        replacement = snapshot()
        replacement["values"]["humidity"] = 67.0
        self.reader.async_fetch_snapshot.side_effect = [
            snapshot(), RuntimeUnavailable("SDK_RPC45_FAILED"), replacement
        ]
        self.assertTrue(await self.refresh())
        self.assertFalse(await self.refresh())
        self.assertTrue(all(not entity.available for entity in self.entities))
        self.assertTrue(await self.refresh())
        self.assertTrue(all(entity.available for entity in self.entities))
        values = {entity._key: entity.native_value for entity in self.entities}
        self.assertEqual(values["humidity"], 67.0)
        self.assertEqual(self.reader.async_fetch_snapshot.await_count, 3)

    async def test_incomplete_batch_marks_every_sensor_unavailable(self):
        bad = snapshot()
        bad["values"].pop("humidity")
        self.reader.async_fetch_snapshot.side_effect = [snapshot(), bad]
        self.assertTrue(await self.refresh())
        self.assertFalse(await self.refresh())
        self.assertTrue(all(not entity.available for entity in self.entities))
        self.assertEqual(self.coordinator.data, VALUES)

    async def test_invalid_first_read_has_no_available_values(self):
        self.reader.async_fetch_snapshot.side_effect = RuntimeUnavailable(
            "SDK_SESSION_FAILED"
        )
        self.assertFalse(await self.refresh())
        self.assertTrue(all(not entity.available for entity in self.entities))
        self.assertTrue(all(entity.native_value is None for entity in self.entities))

    async def test_five_entities_have_distinct_identifiers(self):
        ids = [entity._attr_unique_id for entity in self.entities]
        self.assertEqual(len(set(ids)), 5)
        self.assertTrue(all(value.startswith(DEVICE_ID + "_") for value in ids))


if __name__ == "__main__":
    unittest.main()
