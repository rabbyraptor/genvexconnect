"""Stable five measurements plus opt-in raw RPC45 diagnostic entities."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTemperature, PERCENTAGE, EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSORS, RAW_REGISTERS
from .raw_interpretation import raw_register_attributes

# No controls, setters, service registrations or RPC write operations.


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        *(GenvexRemoteSensor(coordinator, spec) for spec in SENSORS),
        GenvexRemoteDataAge(coordinator),
    ]
    if coordinator.fan_level_v4:
        entities.append(GenvexRemoteFanLevel(coordinator))
    if coordinator.raw_registers_v3:
        entities.extend(
            GenvexRemoteRawRegister(coordinator, spec)
            for spec in RAW_REGISTERS
        )
    async_add_entities(entities)


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


class GenvexRemoteRawRegister(CoordinatorEntity, SensorEntity):
    """Uninterpreted signed int16 from exactly one known RPC45 address.

    No temperature, percentage, RPM, boolean or alarm state is inferred.
    There are 17 raw diagnostics in addition to the five legacy sensors.
    Missing optional register data is unavailable, never reported as zero.
    """

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:code-brackets"

    def __init__(self, coordinator, spec):
        super().__init__(coordinator)
        self._key = "raw_" + spec.key
        self._address = spec.address
        self._attr_unique_id = (
            f"{coordinator.device_id}_rpc45_raw_{spec.address}"
        )
        self._attr_name = f"RPC45 råværdi {spec.address} – {spec.label}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name="Genvex Connect Remote",
            manufacturer="Genvex",
            model="Optima 270",
        )

    @property
    def available(self) -> bool:
        return super().available and self._key in (self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict:
        """Evidence and clearly provisional source display, not a new reading."""
        return raw_register_attributes(self._address, self.native_value)

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data
        return data.get(self._key) if data is not None else None


class GenvexRemoteFanLevel(CoordinatorEntity, SensorEntity):
    """Selected fan step, read directly from RPC42 setpoint address 7."""

    _attr_has_entity_name = True
    _attr_translation_key = "fan_level"
    _attr_icon = "mdi:fan"
    _attr_native_unit_of_measurement = None

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_rpc42_fan_level"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name="Genvex Connect Remote",
            manufacturer="Genvex",
            model="Optima 270",
        )

    @property
    def available(self) -> bool:
        return super().available and "fan_level" in (self.coordinator.data or {})

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data
        return data.get("fan_level") if data is not None else None

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "rpc42_read_object": 0,
            "rpc42_read_address": 7,
            "valid_range": "0-4",
            "measurement_kind": "selected_level_not_fan_percent_or_feedback",
        }
