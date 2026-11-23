"""Genvex Remote integration scaffold — NOT for production installation."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_DEVICE_ID, CONF_PAIR_FROM_APP, CONF_RUNTIME_ENDPOINT, CONF_RUNTIME_TOKEN, CONF_RAW_REGISTERS_V3, CONF_FAN_LEVEL_V4, DOMAIN
from .core_supervisor_loader import async_fetch_paired_token
from .supervisor_pairing import SupervisorPairingUnavailable
from .coordinator import GenvexRemoteCoordinator
from .runtime_client import AuthenticatedSnapshotReader, EXPECTED_V3_APP_ENDPOINT, EXPECTED_V4_APP_ENDPOINT

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
        # Resolve a replacement token only if the App rejects the current
        # in-memory token. Never persist either token to the config entry.
        token_loader = lambda: async_fetch_paired_token(
            hass, device_id=entry.data[CONF_DEVICE_ID],
        )
    else:
        # Existing manually configured entries continue to work unchanged.
        token = entry.data[CONF_RUNTIME_TOKEN]
        token_loader = None
    fan_v4 = entry.options.get(CONF_FAN_LEVEL_V4, False) is True
    raw_v3 = fan_v4 or entry.options.get(CONF_RAW_REGISTERS_V3, False) is True
    reader = AuthenticatedSnapshotReader(
        async_get_clientsession(hass),
        endpoint=(
            EXPECTED_V4_APP_ENDPOINT if fan_v4
            else EXPECTED_V3_APP_ENDPOINT if raw_v3
            else entry.data[CONF_RUNTIME_ENDPOINT]
        ),
        token=token,
        token_loader=token_loader,
    )
    coordinator = GenvexRemoteCoordinator(
        hass, entry.data[CONF_DEVICE_ID], reader,
        raw_registers_v3=raw_v3,
        fan_level_v4=fan_v4,
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
