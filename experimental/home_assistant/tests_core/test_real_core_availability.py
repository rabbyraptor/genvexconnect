"""Real Home Assistant Core coordinator/entity integration contract.

Tested in a *separate* GitHub Actions runner using Home Assistant Core and
pytest-homeassistant, not the production HAOS installation. No Nabto SDK,
network access, credentials, profile or real gateway is required.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

COMPONENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COMPONENT_ROOT))

from custom_components.genvex_remote.coordinator import GenvexRemoteCoordinator
from custom_components.genvex_remote.sensor import GenvexRemoteSensor
from custom_components.genvex_remote.const import SENSORS
from custom_components.genvex_remote.runtime_client import RuntimeUnavailable
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
import logging

DEVICE = "123456789012"
VALUES = {
    "supply_air": 6.7, "outdoor_air": 0.2,
    "exhaust_air": 1.8, "extract_air": 7.8, "humidity": 66.0,
}


def make_snapshot(*, humidity=66.0, complete=True):
    readings = {**VALUES, "humidity": humidity}
    if not complete:
        readings.pop("humidity")
    return {
        "schema_version": 1,
        "device_id": DEVICE,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "health": "ok",
        "values": readings,
    }


@pytest.mark.asyncio
async def test_core_coordinator_all_five_unavailable_and_recover(hass):
    """Real HA DataUpdateCoordinator + CoordinatorEntity property behavior."""
    reader = SimpleNamespace(async_fetch_snapshot=AsyncMock(side_effect=[
        make_snapshot(), RuntimeUnavailable("private-session-detail"),
        make_snapshot(humidity=67.0),
    ]))
    coordinator = GenvexRemoteCoordinator(hass, DEVICE, reader)
    entities = [GenvexRemoteSensor(coordinator, spec) for spec in SENSORS]
    assert len(entities) == 5

    await coordinator.async_refresh()
    assert coordinator.last_update_success is True
    assert all(entity.available for entity in entities)
    assert {entity._key: entity.native_value for entity in entities} == VALUES

    await coordinator.async_refresh()
    assert coordinator.last_update_success is False
    assert all(not entity.available for entity in entities)

    await coordinator.async_refresh()
    assert coordinator.last_update_success is True
    assert all(entity.available for entity in entities)
    assert {entity._key: entity.native_value for entity in entities} == {
        **VALUES, "humidity": 67.0,
    }
    assert reader.async_fetch_snapshot.await_count == 3


@pytest.mark.asyncio
async def test_core_rejects_incomplete_batch_as_unavailable(hass):
    reader = SimpleNamespace(async_fetch_snapshot=AsyncMock(
        side_effect=[make_snapshot(), make_snapshot(complete=False)]
    ))
    coordinator = GenvexRemoteCoordinator(hass, DEVICE, reader)
    entities = [GenvexRemoteSensor(coordinator, spec) for spec in SENSORS]
    await coordinator.async_refresh()
    assert all(entity.available for entity in entities)
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False
    assert all(not entity.available for entity in entities)

@pytest.mark.asyncio
async def test_actual_hass_states_success_unavailable_recovery(hass):
    """Register real SensorEntity objects in Core's state machine."""
    reader = SimpleNamespace(async_fetch_snapshot=AsyncMock(side_effect=[
        make_snapshot(), RuntimeUnavailable("secret-never-in-states"),
        make_snapshot(humidity=67.0),
    ]))
    coordinator = GenvexRemoteCoordinator(hass, DEVICE, reader)
    entities = [GenvexRemoteSensor(coordinator, spec) for spec in SENSORS]

    await coordinator.async_refresh()
    component = EntityComponent(logging.getLogger(__name__), SENSOR_DOMAIN, hass)
    await component.async_add_entities(entities)
    await hass.async_block_till_done()
    entity_ids = [entity.entity_id for entity in entities]
    assert len(set(entity_ids)) == 5
    assert all(entity_id.startswith("sensor.") for entity_id in entity_ids)
    assert all(hass.states.get(entity_id) is not None for entity_id in entity_ids)
    assert all(hass.states.get(entity_id).state != STATE_UNAVAILABLE for entity_id in entity_ids)

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert all(hass.states.get(entity_id).state == STATE_UNAVAILABLE
               for entity_id in entity_ids)
    assert all("secret-never-in-states" not in str(hass.states.get(entity_id))
               for entity_id in entity_ids)

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert all(hass.states.get(entity_id).state != STATE_UNAVAILABLE
               for entity_id in entity_ids)
    assert hass.states.get(entities[4].entity_id).state == "67"
    assert reader.async_fetch_snapshot.await_count == 3


@pytest.mark.asyncio
async def test_actual_hass_states_incomplete_snapshot_unavailable(hass):
    reader = SimpleNamespace(async_fetch_snapshot=AsyncMock(side_effect=[
        make_snapshot(), make_snapshot(complete=False)
    ]))
    coordinator = GenvexRemoteCoordinator(hass, DEVICE, reader)
    entities = [GenvexRemoteSensor(coordinator, spec) for spec in SENSORS]
    await coordinator.async_refresh()
    component = EntityComponent(logging.getLogger(__name__), SENSOR_DOMAIN, hass)
    await component.async_add_entities(entities)
    await hass.async_block_till_done()
    entity_ids = [entity.entity_id for entity in entities]
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert all(hass.states.get(entity_id).state == STATE_UNAVAILABLE
               for entity_id in entity_ids)
