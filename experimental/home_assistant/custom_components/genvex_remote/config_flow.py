"""Device-ID setup scaffold for future UI onboarding.

Do NOT request the account password until an authenticated App bridge and
vendor-CA validation are ready. A user cannot mistakenly enroll here.
"""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries
import voluptuous as vol

from .const import (CONF_DEVICE_ID, CONF_RUNTIME_ENDPOINT, CONF_RUNTIME_TOKEN, DOMAIN, valid_device_id)
from .runtime_client import validate_private_endpoint


class GenvexRemoteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Capture only non-secret device identity in the early development build."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]
            if not valid_device_id(device_id):
                errors["base"] = "invalid_device_id"
            else:
                try:
                    validate_private_endpoint(user_input[CONF_RUNTIME_ENDPOINT])
                    token = user_input[CONF_RUNTIME_TOKEN]
                    if not isinstance(token, str) or not 40 <= len(token) <= 128 or not token.isascii():
                        raise ValueError
                except ValueError:
                    errors["base"] = "invalid_runtime_config"
                else:
                    await self.async_set_unique_id(device_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"Genvex Remote {device_id[-4:]}",
                        data={CONF_DEVICE_ID: device_id,
                              CONF_RUNTIME_ENDPOINT: user_input[CONF_RUNTIME_ENDPOINT],
                              CONF_RUNTIME_TOKEN: token},
                    )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE_ID): str,
                vol.Required(CONF_RUNTIME_ENDPOINT): str,
                vol.Required(CONF_RUNTIME_TOKEN): str,
            }),
            errors=errors,
        )
