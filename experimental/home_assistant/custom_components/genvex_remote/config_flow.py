"""Separate read-only App IPC onboarding with explicit Core pairing."""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .const import (CONF_DEVICE_ID, CONF_PAIR_FROM_APP, CONF_RUNTIME_ENDPOINT, CONF_RUNTIME_TOKEN, DOMAIN, valid_device_id)
from .core_supervisor_loader import async_fetch_paired_token
from .runtime_client import EXPECTED_APP_ENDPOINT
from .supervisor_pairing import SupervisorPairingUnavailable



class GenvexRemoteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Use a fixed App endpoint; allow explicit Core-based token pairing."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Configure Core pairing for an existing Genvex Remote entry."""
        from .pairing_options import GenvexRemoteOptionsFlow

        return GenvexRemoteOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            device_id = user_input.get(CONF_DEVICE_ID)
            if not valid_device_id(device_id):
                errors["base"] = "invalid_device_id"
            elif type(user_input.get(CONF_PAIR_FROM_APP, False)) is not bool:
                errors["base"] = "invalid_runtime_config"
            else:
                token = user_input.get(CONF_RUNTIME_TOKEN)
                if user_input.get(CONF_PAIR_FROM_APP) is True:
                    try:
                        token = await async_fetch_paired_token(
                            self.hass, device_id=device_id,
                        )
                    except SupervisorPairingUnavailable:
                        errors["base"] = "app_pairing_unavailable"
                if not errors:
                    if (
                        type(token) is not str
                        or not 40 <= len(token) <= 128
                        or not token.isascii()
                        or any(char in token for char in "\r\n\x00")
                    ):
                        errors["base"] = "invalid_runtime_config"
                    else:
                        await self.async_set_unique_id(device_id)
                        self._abort_if_unique_id_configured()
                        # Core-paired entries never persist a copy of the
                        # App's IPC secret. Setup resolves it again from
                        # trusted Supervisor state on every entry reload.
                        entry_data = {
                            CONF_DEVICE_ID: device_id,
                            CONF_RUNTIME_ENDPOINT: EXPECTED_APP_ENDPOINT,
                        }
                        if user_input.get(CONF_PAIR_FROM_APP) is True:
                            entry_data[CONF_PAIR_FROM_APP] = True
                        else:
                            entry_data[CONF_RUNTIME_TOKEN] = token
                        return self.async_create_entry(
                            title=f"Genvex Remote {device_id[-4:]}",
                            data=entry_data,
                        )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE_ID): str,
                vol.Optional(CONF_PAIR_FROM_APP, default=False): bool,
                vol.Optional(CONF_RUNTIME_TOKEN): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
            }),
            errors=errors,
        )
