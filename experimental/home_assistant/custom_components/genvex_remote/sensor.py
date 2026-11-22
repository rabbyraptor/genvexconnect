"""First five remote sensor entities, all read-only."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTemperature, PERCENTAGE
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSORS

# No controls, setters, service registrations or RPC write operations.


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([\n        *(GenvexRemoteSensor(coordinator, spec) for spec in SENSORS),\n        GenvexRemoteDataAge(coordinator),\n    ])


class GenvexRemoteSensor(CoordinatorEntity, SensorEntity):
    """One field from the latest validated five-value batch."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, spec):
        super().__init__(coordinator)
        self._key = spec.key
        self._attr_unique_id = f"{coordinator.device_id}_{spec.key}"
        self._attr_translation_key = spec.translation_key
        self._attr_native_unit_of_measurement = (
            PERCENTAGE if spec.key == "humidity" else UnitOfTemperature.CELSIUS
        )
        self._attr_device_class = (
            SensorDeviceClass.HUMIDITY if spec.key == "humidity"
            else SensorDeviceClass.TEMPERATURE
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name="Genvex Connect Remote",
            manufacturer="Genvex",
            model="Optima 270",
        )

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        return data.get(self._key) if data is not None else None


class GenvexRemoteDataAge(CoordinatorEntity, SensorEntity):
    """Unobtrusive diagnostic showing the age of the gateway measurement."""

    _attr_has_entity_name = True
    _attr_translation_key = "data_age"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "min"
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_data_age"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name="Genvex Connect Remote",
            manufacturer="Genvex",
            model="Optima 270",
        )

    @property
    def native_value(self) -> float | None:
        age = self.coordinator.data_age_seconds
        return round(age / 60, 1) if age is not None else None
