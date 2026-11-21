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
