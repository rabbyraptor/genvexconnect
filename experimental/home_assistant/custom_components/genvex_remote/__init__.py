"""Genvex Remote integration scaffold — NOT for production installation."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_DEVICE_ID, CONF_PAIR_FROM_APP, CONF_RUNTIME_ENDPOINT, CONF_RUNTIME_TOKEN, DOMAIN
from .core_supervisor_loader import async_fetch_paired_token
from .supervisor_pairing import SupervisorPairingUnavailable
from .coordinator import GenvexRemoteCoordinator
from .runtime_client import AuthenticatedSnapshotReader

PLATFORMS = (Platform.SENSOR,)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Fetch only authenticated snapshots from an explicitly configured App."""
    if entry.options.get(CONF_PAIR_FROM_APP, entry.data.get(CONF_PAIR_FROM_APP, False)) is True:
        try:
            token = await async_fetch_paired_token(
                hass, device_id=entry.data[CONF_DEVICE_ID],
            )
        except SupervisorPairingUnavailable:
            raise ConfigEntryNotReady(
                "Genvex Remote App pairing unavailable"
            ) from None
    else:
        # Existing manually configured entries continue to work unchanged.
        token = entry.data[CONF_RUNTIME_TOKEN]
    reader = AuthenticatedSnapshotReader(
        async_get_clientsession(hass),
        endpoint=entry.data[CONF_RUNTIME_ENDPOINT],
        token=token,
    )
    coordinator = GenvexRemoteCoordinator(
        hass, entry.data[CONF_DEVICE_ID], reader,
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
