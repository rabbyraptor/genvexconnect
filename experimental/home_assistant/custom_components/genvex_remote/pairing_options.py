"""Explicit, one-entry transition from manual IPC token to Core pairing.

The options flow keeps the existing config entry and stable entity IDs.
It verifies the started App before committing the switch. Core-paired
entries never persist a copy of the IPC bearer token.
"""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.helpers.selector import (
    TextSelector, TextSelectorConfig, TextSelectorType,
)
import voluptuous as vol

from .const import (
    CONF_DEVICE_ID, CONF_PAIR_FROM_APP, CONF_RUNTIME_TOKEN,
    CONF_RAW_REGISTERS_V3, CONF_FAN_LEVEL_V4,
)
from .core_supervisor_loader import async_fetch_paired_token
from .supervisor_pairing import SupervisorPairingUnavailable


def _valid_ipc_token(token: object) -> bool:
    return (
        type(token) is str and 40 <= len(token) <= 128
        and token.isascii()
        and not any(char in token for char in "\r\n\x00")
    )


class GenvexRemoteOptionsFlow(config_entries.OptionsFlowWithReload):
    """Switch authentication for an existing entry after explicit opt-in."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        entry = self.config_entry
        existing_auto = (
            entry.options.get(CONF_PAIR_FROM_APP, 
                              entry.data.get(CONF_PAIR_FROM_APP, False)) is True
        )
        existing_raw = entry.options.get(CONF_RAW_REGISTERS_V3, False) is True
        existing_fan = entry.options.get(CONF_FAN_LEVEL_V4, False) is True
        errors: dict[str, str] = {}
        if user_input is not None:
            requested_auto = user_input.get(CONF_PAIR_FROM_APP, False)
            requested_raw = user_input.get(CONF_RAW_REGISTERS_V3, existing_raw)
            requested_fan = user_input.get(CONF_FAN_LEVEL_V4, existing_fan)
            if requested_fan is True:
                requested_raw = True
            if (type(requested_auto) is not bool or type(requested_raw) is not bool
                    or type(requested_fan) is not bool):
                errors["base"] = "invalid_runtime_config"
            elif requested_auto:
                try:
                    token = await async_fetch_paired_token(
                        self.hass, device_id=entry.data[CONF_DEVICE_ID],
                    )
                    if not _valid_ipc_token(token):
                        raise SupervisorPairingUnavailable(
                            "Trusted App pairing unavailable"
                        )
                except SupervisorPairingUnavailable:
                    errors["base"] = "app_pairing_unavailable"
                if not errors:
                    data = dict(entry.data)
                    data.pop(CONF_RUNTIME_TOKEN, None)
                    data.pop(CONF_PAIR_FROM_APP, None)
                    self.hass.config_entries.async_update_entry(entry, data=data)
                    options = {CONF_PAIR_FROM_APP: True}
                    if requested_raw:
                        options[CONF_RAW_REGISTERS_V3] = True
                    if requested_fan:
                        options[CONF_FAN_LEVEL_V4] = True
                    return self.async_create_entry(
                        title="", data=options,
                    )
            else:
                # A manual entry may keep its existing token if the field is
                # blank. Reversing Core pairing requires a *new* manual token.
                token = user_input.get(CONF_RUNTIME_TOKEN)
                if token in (None, "") and not existing_auto:
                    token = entry.data.get(CONF_RUNTIME_TOKEN)
                if not _valid_ipc_token(token):
                    errors["base"] = "invalid_runtime_config"
                else:
                    data = dict(entry.data)
                    data[CONF_RUNTIME_TOKEN] = token
                    data.pop(CONF_PAIR_FROM_APP, None)
                    self.hass.config_entries.async_update_entry(entry, data=data)
                    options = {CONF_PAIR_FROM_APP: False}
                    if requested_raw:
                        options[CONF_RAW_REGISTERS_V3] = True
                    return self.async_create_entry(
                        title="", data=options,
                    )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_PAIR_FROM_APP, default=existing_auto,
                ): bool,
                vol.Optional(
                    CONF_RAW_REGISTERS_V3, default=existing_raw,
                ): bool,
                vol.Optional(
                    CONF_FAN_LEVEL_V4, default=existing_fan,
                ): bool,
                vol.Optional(CONF_RUNTIME_TOKEN): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
            }),
            errors=errors,
        )
