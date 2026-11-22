"""Offline-verified Supervisor App options token extraction (Core-only).

This module does NOT call the Supervisor, read an environment token, or change
App configuration. A trusted Home Assistant Core API adapter must supply the
authenticated /addons/<app>/info response. Do not use from an App: the options
of another App are redacted unless the caller is Core or privileged.

The extract function deliberately never logs raw Supervisor data, the token,
the configured device ID or other sensitive option values.
"""
from __future__ import annotations

from collections.abc import Mapping

APP_ID = "local_genvex_nabto_remote"


class SupervisorPairingUnavailable(ValueError):
    """Supervisor App metadata cannot yield a trusted live IPC token."""


def extract_app_ipc_token(payload: object, *, expected_device_id: str) -> str:
    """Validate one authenticated Core-fetched App record and return token.

    This is a narrow, pure function. It makes no claim about the caller's
    authorization: the future transport is responsible for authenticating Core.
    """
    try:
        if (type(expected_device_id) is not str
                or len(expected_device_id) != 12
                or not expected_device_id.isascii()
                or not expected_device_id.isdecimal()):
            raise ValueError
        if not isinstance(payload, Mapping) or payload.get("result") != "ok":
            raise ValueError
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise ValueError
        if (data.get("slug") != APP_ID
                or data.get("state") != "started"):
            raise ValueError
        options = data.get("options")
        if not isinstance(options, Mapping):
            raise ValueError
        if options.get("device_id") != expected_device_id:
            raise ValueError
        token = options.get("ipc_token")
        if (type(token) is not str or not 40 <= len(token) <= 128
                or not token.isascii()
                or any(char in token for char in "\r\n\x00")):
            raise ValueError
        return token
    except (ValueError, TypeError):
        raise SupervisorPairingUnavailable("Trusted App pairing unavailable") from None
