"""Core-owned Supervisor App metadata adapter for explicit Genvex pairing.

Uses Home Assistant's existing authenticated Supervisor client (Unix socket
when available), never a user URL, an environment token or a new HTTP API.
The single requested slug is fixed and only two required options are projected.
"""
from __future__ import annotations

from .supervisor_pairing import (
    APP_ID,
    SupervisorPairingUnavailable,
    async_load_app_ipc_token,
)


async def async_fetch_paired_token(hass: object, *, device_id: str) -> str:
    """Obtain the fixed started App's IPC token through Core's Supervisor API."""
    async def load_app(slug: str) -> object:
        if slug != APP_ID:
            raise SupervisorPairingUnavailable("Trusted App pairing unavailable")
        # Lazy import lets the whole integration be imported on non-HAOS
        # installations. The caller handles an unavailable Supervisor as a
        # normal pairing failure, not as a reason to store fake credentials.
        from homeassistant.components.hassio import get_supervisor_client

        addon = await get_supervisor_client(hass).addons.addon_info(APP_ID)
        # Project only required fields: never return identity, unlock_secret,
        # passwords, raw metadata, or a serialized complete Addon model.
        options = addon.options
        if not isinstance(options, dict):
            raise SupervisorPairingUnavailable("Trusted App pairing unavailable")
        return {
            "result": "ok",
            "data": {
                "slug": addon.slug,
                "state": addon.state,
                "options": {
                    "device_id": options.get("device_id"),
                    "ipc_token": options.get("ipc_token"),
                },
            },
        }

    return await async_load_app_ipc_token(
        load_app, expected_device_id=device_id,
    )
