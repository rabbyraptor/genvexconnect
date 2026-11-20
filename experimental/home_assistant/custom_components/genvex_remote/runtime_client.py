"""Abstract bridge to the separately isolated Nabto runtime.

This integration intentionally contains no Nabto SDK, credential, local
UDP operations, HTTP listener, or vendor registration calls. An authenticated
runtime IPC backend must be implemented and security reviewed before enabling
this integration in HAOS. No mock readings or cached test values.
"""
from __future__ import annotations

from typing import Any, Protocol


class RuntimeUnavailable(Exception):
    """No functioning trusted App -> HA snapshot channel exists."""


class SnapshotReader(Protocol):
    """A future authenticated read-only client implements this interface."""

    async def async_fetch_snapshot(self, device_id: str) -> dict[str, Any]:
        """Return a fresh snapshot document from the trusted runtime."""


class UnconfiguredReader:
    """Safe default, fails closed instead of inventing live sensor data."""

    async def async_fetch_snapshot(self, device_id: str) -> dict[str, Any]:
        raise RuntimeUnavailable("The authenticated Nabto runtime bridge is not installed")

class HTTPResponse(Protocol):
    """Minimal async HTTP response surface for injected aiohttp transport."""

    status: int

    async def read(self) -> bytes:
        """Read the bounded HTTP response body."""


class HTTPRequestContext(Protocol):
    async def __aenter__(self) -> HTTPResponse: ...
    async def __aexit__(self, exc_type, exc, tb) -> None: ...


class HTTPSession(Protocol):
    def get(self, url: str, *, headers: dict[str, str]) -> HTTPRequestContext: ...


class AuthenticatedSnapshotReader:
    """Fail-closed HTTP consumer, usable only after trusted provisioning.

    This is a transport component, not automatic discovery/onboarding.
    The future HA setup must provide a trusted Supervisor-internal endpoint
    and a securely provisioned token. No config-flow password is stored here.
    """

    def __init__(
        self, session: HTTPSession, *, endpoint: str, token: str,
    ) -> None:
        from urllib.parse import urlsplit

        try:
            parsed = urlsplit(endpoint)
            host = parsed.hostname or ""
            port = parsed.port
        except ValueError:
            raise ValueError("Invalid internal snapshot endpoint") from None
        if (parsed.scheme != "http" or not host or port is None
                or parsed.path != "/v1/snapshot" or parsed.username
                or parsed.password or parsed.query or parsed.fragment
                or len(host) > 253 or not host.isascii()
                or not all(ch.isalnum() or ch in "-_." for ch in host)
                or not (1 <= port <= 65535)):
            raise ValueError("Invalid internal snapshot endpoint")
        if not isinstance(token, str) or not 40 <= len(token) <= 128 or not token.isascii():
            raise ValueError("Invalid internal transport token")
        self._session = session
        self._url = endpoint
        self._token = token

    async def async_fetch_snapshot(self, device_id: str) -> dict[str, Any]:
        """Fetch exactly one bounded JSON snapshot without retry or token logging."""
        import asyncio
        import json
        try:
            async with asyncio.timeout(8):
                async with self._session.get(
                    self._url,
                    headers={"Authorization": "Bearer " + self._token,
                             "Accept": "application/json"},
                ) as response:
                    if response.status != 200:
                        raise RuntimeUnavailable("Runtime snapshot unavailable")
                    # The production aiohttp adapter should additionally reject
                    # oversized responses before buffering the full body.
                    body = await response.read()
                    if len(body) > 4096:
                        raise RuntimeUnavailable("Runtime snapshot unavailable")
                    document = json.loads(body)
                    if not isinstance(document, dict):
                        raise ValueError("Invalid snapshot")
                    return document
        except RuntimeUnavailable:
            raise
        except Exception:
            # Never surface URL, token, raw HTTP error or SDK details.
            raise RuntimeUnavailable("Runtime snapshot unavailable") from None
