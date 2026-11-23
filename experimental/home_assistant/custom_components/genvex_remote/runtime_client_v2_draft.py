"""Uninstalled, fail-closed v2 Home Assistant HTTP reader draft.

No Home Assistant imports, SDK, device writes, auto configuration or service
registration. Does not modify the active five-sensor v1 runtime client.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from .runtime_client import HTTPSession, RuntimeUnavailable
from .snapshot_v2_draft import validate_v2_snapshot

EXPECTED_V2_APP_ENDPOINT = "http://local-genvex-nabto-remote:18275/v2/snapshot"
_MAX_BODY = 4096


class V2AuthenticatedSnapshotReader:
    """Read an exact, token-protected, bounded v2 document without retry."""

    def __init__(self, session: HTTPSession, *, endpoint: str, token: str):
        if endpoint != EXPECTED_V2_APP_ENDPOINT:
            raise ValueError("Invalid private v2 endpoint")
        if (
            not isinstance(token, str)
            or not 40 <= len(token) <= 128
            or not token.isascii()
        ):
            raise ValueError("Invalid private IPC token")
        self._session = session
        self._token = token

    async def async_fetch_snapshot(self, device_id: str) -> dict[str, Any]:
        """Obtain a bounded JSON object, validate later with known device ID."""
        try:
            async with asyncio.timeout(8):
                async with self._session.get(
                    EXPECTED_V2_APP_ENDPOINT,
                    headers={
                        "Authorization": "Bearer " + self._token,
                        "Accept": "application/json",
                    },
                    allow_redirects=False,
                ) as response:
                    if response.status != 200:
                        raise RuntimeUnavailable("V2 snapshot unavailable")
                    if (
                        response.content_length is not None
                        and response.content_length > _MAX_BODY
                    ):
                        raise RuntimeUnavailable("V2 snapshot unavailable")
                    raw = await response.content.read(_MAX_BODY + 1)
                    if len(raw) > _MAX_BODY:
                        raise RuntimeUnavailable("V2 snapshot unavailable")
                    result = json.loads(raw)
                    if type(result) is not dict:
                        raise ValueError("Invalid JSON object")
                    # Do not return wrong-device, stale or malformed snapshots.
                    validate_v2_snapshot(
                        result, expected_device_id=device_id
                    )
                    return result
        except RuntimeUnavailable:
            raise
        except Exception:
            # No URL, credentials, provider body or diagnostic detail in errors.
            raise RuntimeUnavailable("V2 snapshot unavailable") from None
