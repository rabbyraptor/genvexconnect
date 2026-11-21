"""Isolated Home Assistant Core config-entry lifecycle integration test.

A *real* config entry and entity/device registries are used. Only the
private transport reader is a finite offline fake. The source integration
is copied inside the ephemeral pytest Home Assistant config directory,
never installed on the operator's HAOS system.
"""
from __future__ import annotations

from pathlib import Path
from shutil import copytree
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant.common import MockConfigEntry

from custom_components.genvex_remote.const import (
    CONF_DEVICE_ID, CONF_RUNTIME_ENDPOINT, CONF_RUNTIME_TOKEN, DOMAIN, SENSORS,
)
from custom_components.genvex_remote.runtime_client import EXPECTED_APP_ENDPOINT, RuntimeUnavailable
from test_real_core_availability import DEVICE, make_snapshot

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / DOMAIN


@pytest.mark.asyncio
async def test_config_entry_setup_runtime_failure_recovery_and_unload(hass, enable_custom_integrations):
    """Exercise the installed custom integration through HA config entry APIs."""
    target = Path(hass.config.path("custom_components", DOMAIN))
    await hass.async_add_executor_job(copytree, COMPONENT, target)

    reader = SimpleNamespace(async_fetch_snapshot=AsyncMock(side_effect=[
        make_snapshot(),
        make_snapshot(humidity=67.0),
        RuntimeUnavailable("private-transport-details"),
        make_snapshot(humidity=68.0),
    ]))
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Genvex Remote test",
        unique_id=DEVICE,
        data={
            CONF_DEVICE_ID: DEVICE,
            CONF_RUNTIME_ENDPOINT: EXPECTED_APP_ENDPOINT,
            CONF_RUNTIME_TOKEN: "T" * 48,
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.genvex_remote.AuthenticatedSnapshotReader",
        return_value=reader,
    ), patch(
        "custom_components.genvex_remote.async_get_clientsession",
        return_value=object(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

        registry = er.async_get(hass)
        entity_entries = er.async_entries_for_config_entry(registry, entry.entry_id)
        assert len(entity_entries) == len(SENSORS) == 5
        ids = [item.entity_id for item in entity_entries]
        assert all(hass.states.get(entity_id) is not None for entity_id in ids)

        devices = dr.async_get(hass)
        registered = dr.async_entries_for_config_entry(devices, entry.entry_id)
        assert len(registered) == 1
        assert (DOMAIN, DEVICE) in registered[0].identifiers
        assert all(item.device_id == registered[0].id for item in entity_entries)

        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert all(hass.states.get(entity_id).state != STATE_UNAVAILABLE for entity_id in ids)

        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert all(hass.states.get(entity_id).state == STATE_UNAVAILABLE for entity_id in ids)
        assert all("private-transport-details" not in str(hass.states.get(entity_id))
                   for entity_id in ids)

        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert all(hass.states.get(entity_id).state != STATE_UNAVAILABLE for entity_id in ids)

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.NOT_LOADED
        assert entry.entry_id not in hass.data.get(DOMAIN, {})
        assert all(hass.states.get(entity_id) is None for entity_id in ids)
