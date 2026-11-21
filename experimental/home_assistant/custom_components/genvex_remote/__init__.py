"""Genvex Remote integration scaffold — NOT for production installation."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_DEVICE_ID, CONF_RUNTIME_ENDPOINT, CONF_RUNTIME_TOKEN, DOMAIN
from .coordinator import GenvexRemoteCoordinator
from .runtime_client import AuthenticatedSnapshotReader

PLATFORMS = (Platform.SENSOR,)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Fetch only authenticated snapshots from an explicitly configured App."""
    reader = AuthenticatedSnapshotReader(
        async_get_clientsession(hass),
        endpoint=entry.data[CONF_RUNTIME_ENDPOINT],
        token=entry.data[CONF_RUNTIME_TOKEN],
    )
    coordinator = GenvexRemoteCoordinator(
        hass, entry.data[CONF_DEVICE_ID], reader, config_entry=entry,
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the isolated remote integration without touching LAN devices."""
    result = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if result:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return result
