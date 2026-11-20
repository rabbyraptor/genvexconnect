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
        validate_private_endpoint(endpoint)
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

def validate_private_endpoint(endpoint: str) -> None:
    """Only accept private App DNS names or literal loopback/private IPs."""
    from ipaddress import ip_address
    from urllib.parse import urlsplit

    if not isinstance(endpoint, str) or len(endpoint) > 512:
        raise ValueError("Invalid private runtime endpoint")
    try:
        parsed = urlsplit(endpoint)
        host = parsed.hostname or ""
        port = parsed.port
        ip = None
        try:
            ip = ip_address(host)
        except ValueError:
            pass
    except ValueError:
        raise ValueError("Invalid private runtime endpoint") from None
    if (parsed.scheme != "http" or port != 18275
            or parsed.path != "/v1/snapshot" or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or not host or not host.isascii() or len(host) > 253):
        raise ValueError("Invalid private runtime endpoint")
    if ip is not None:
        if not (ip.is_private or ip.is_loopback) or ip.is_unspecified:
            raise ValueError("Endpoint must be on a private network")
    elif (not all(c.isalnum() or c in "-_." for c in host)
          or "." in host or not host.startswith("app_")):
        # Restrict to HAOS App hostnames; do not send bearer tokens to
        # arbitrary public DNS names.
        raise ValueError("Endpoint must be a HAOS App hostname")
