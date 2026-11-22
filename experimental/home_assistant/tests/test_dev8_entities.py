"""DEV8.3 Home Assistant sensor registration regression without HA runtime."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from test_snapshot import HERE


class _CoordinatorEntity:
    def __init__(self, coordinator):
        self.coordinator = coordinator

    @property
    def available(self):
        return True


class EntityRegistrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        ha = types.ModuleType("homeassistant")
        components = types.ModuleType("homeassistant.components")
        sensor = types.ModuleType("homeassistant.components.sensor")
        sensor.SensorEntity = type("SensorEntity", (), {})
        sensor.SensorDeviceClass = types.SimpleNamespace(
            HUMIDITY="humidity", TEMPERATURE="temperature",
        )
        sensor.SensorStateClass = types.SimpleNamespace(MEASUREMENT="measurement")
        const = types.ModuleType("homeassistant.const")
        const.UnitOfTemperature = types.SimpleNamespace(CELSIUS="°C")
        const.PERCENTAGE = "%"
        const.EntityCategory = types.SimpleNamespace(DIAGNOSTIC="diagnostic")
        helpers = types.ModuleType("homeassistant.helpers")
        devices = types.ModuleType("homeassistant.helpers.device_registry")
        devices.DeviceInfo = lambda **data: data
        coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")
        coordinator.CoordinatorEntity = _CoordinatorEntity
        self.modules = patch.dict(sys.modules, {
            "homeassistant": ha,
            "homeassistant.components": components,
            "homeassistant.components.sensor": sensor,
            "homeassistant.const": const,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.device_registry": devices,
            "homeassistant.helpers.update_coordinator": coordinator,
        })
        self.modules.start()
        self.addCleanup(self.modules.stop)
        spec = importlib.util.spec_from_file_location(
            "dev_remote.sensor", HERE / "sensor.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.sensor = module
        self.entry = types.SimpleNamespace(entry_id="raw-test")
        self.coordinator = types.SimpleNamespace(
            device_id="123456789012", raw_registers_v3=True,
            data={
                "supply_air": 6.8, "outdoor_air": 0.8,
                "exhaust_air": 2.2, "extract_air": 7.8,
                "humidity": 67.0, "raw_supply_air": 368,
                "raw_humidity": 67, "raw_fan_duty_supply": 6000,
                "raw_alarm_word_1_raw": 0,
            },
            data_age_seconds=60,
        )
        self.hass = types.SimpleNamespace(data={
            "genvex_remote": {self.entry.entry_id: self.coordinator},
        })

    async def entities(self):
        found = []
        await self.sensor.async_setup_entry(
            self.hass, self.entry, lambda entities: found.extend(entities),
        )
        return found

    async def test_opt_in_registers_existing_six_plus_seventeen_raw(self):
        entities = await self.entities()
        self.assertEqual(len(entities), 23)
        existing = entities[:5]
        self.assertEqual(
            [item._attr_unique_id for item in existing],
            [f"123456789012_{key}" for key in (
                "supply_air", "outdoor_air", "exhaust_air",
                "extract_air", "humidity",
            )],
        )
        raw = entities[6:]
        self.assertEqual(len(raw), 17)
        self.assertEqual(len({e._attr_unique_id for e in raw}), 17)
        self.assertEqual(
            [item._attr_unique_id for item in raw],
            ["123456789012_rpc45_raw_" + str(addr) for addr in (
                20, 21, 22, 23, 26, 24, 18, 19, 35, 36, 41, 42,
                53, 40, 114, 115, 50,
            )],
        )
        self.assertTrue(all(
            e._attr_entity_category == "diagnostic" for e in raw
        ))
        self.assertTrue(all("råværdi" in e._attr_name for e in raw))
        self.assertEqual(raw[6]._attr_unique_id, "123456789012_rpc45_raw_18")
        self.assertEqual(raw[6].native_value, 6000)
        self.assertEqual(raw[14].native_value, 0)
        self.assertTrue(raw[6].available)
        self.assertFalse(raw[7].available)
        self.assertIsNone(raw[7].native_value)
        self.assertIsNone(raw[7]._attr_native_unit_of_measurement
                          if hasattr(raw[7], "_attr_native_unit_of_measurement")
                          else None)

    async def test_default_v1_retains_only_original_six_entities(self):
        self.coordinator.raw_registers_v3 = False
        entities = await self.entities()
        self.assertEqual(len(entities), 6)
        self.assertEqual(entities[0].native_value, 6.8)
        self.assertEqual(entities[-1].native_value, 1.0)


if __name__ == "__main__":
    unittest.main()
