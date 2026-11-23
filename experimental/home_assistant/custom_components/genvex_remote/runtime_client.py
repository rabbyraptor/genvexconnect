"""Abstract bridge to the separately isolated Nabto runtime.

This integration intentionally contains no Nabto SDK, credential, local
UDP operations, HTTP listener, or vendor registration calls. An authenticated
runtime IPC backend must be implemented and security reviewed before enabling
this integration in HAOS. No mock readings or cached test values.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any, Protocol


class RuntimeUnavailable(Exception):
    """No functioning trusted App -> HA snapshot channel exists."""


class RuntimeAuthenticationFailed(RuntimeUnavailable):
    """Only an explicit 401/403 response can trigger token re-pairing."""


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
    def get(self, url: str, *, headers: dict[str, str], allow_redirects: bool = False) -> HTTPRequestContext: ...


SNAPSHOT_REQUEST_TIMEOUT_SECONDS = 20
TOKEN_REFRESH_TIMEOUT_SECONDS = 12


def _valid_runtime_token(token: object) -> bool:
    """Check header-safe token shape both on setup and after rotation."""
    return (
        type(token) is str
        and 40 <= len(token) <= 128
        and token.isascii()
        and not any(char in token for char in "\r\n\x00")
    )


class AuthenticatedSnapshotReader:
    """Pinned read-only App IPC with bounded in-session token recovery.

    When Core pairing is enabled, a 401/403 can refresh the in-memory token
    from the authenticated Supervisor client. Each failed read is retried
    at most once; transport errors never trigger a Supervisor lookup.
    """

    def __init__(
        self,
        session: HTTPSession,
        *,
        endpoint: str,
        token: str,
        token_loader: Callable[[], Awaitable[str]] | None = None,
    ) -> None:
        validate_private_endpoint(endpoint)
        if not _valid_runtime_token(token):
            raise ValueError("Invalid internal transport token")
        if token_loader is not None and not callable(token_loader):
            raise ValueError("Invalid token loader")
        self._session = session
        self._url = endpoint
        self._token = token
        self._token_loader = token_loader
        # Concurrent callers discovering the same expired token perform
        # only one Supervisor lookup, then reuse the new in-memory token.
        self._refresh_lock = asyncio.Lock()

    async def async_fetch_snapshot(self, device_id: str) -> dict[str, Any]:
        """One IPC read, optionally one trusted token refresh and retry."""
        attempted_token = self._token
        try:
            return await self._fetch_once(attempted_token)
        except RuntimeAuthenticationFailed:
            if self._token_loader is None:
                raise RuntimeUnavailable("Runtime snapshot unavailable") from None

        async with self._refresh_lock:
            if self._token == attempted_token:
                try:
                    # The real Core Supervisor adapter is independently
                    # bounded to ten seconds; this bounds injected loaders.
                    async with asyncio.timeout(TOKEN_REFRESH_TIMEOUT_SECONDS):
                        replacement = await self._token_loader()
                    if not _valid_runtime_token(replacement) or replacement == attempted_token:
                        raise ValueError("No valid replacement token")
                except Exception:
                    # Do not leak Supervisor metadata, credentials or
                    # transport exceptions into the coordinator or logs.
                    raise RuntimeUnavailable("Runtime snapshot unavailable") from None
                self._token = replacement

        try:
            return await self._fetch_once(self._token)
        except RuntimeAuthenticationFailed:
            # No recursion or unbounded retry on repeated 401/403.
            raise RuntimeUnavailable("Runtime snapshot unavailable") from None

    async def _fetch_once(self, token: str) -> dict[str, Any]:
        """One bounded request with no redirects, error body or URL leakage."""
        try:
            async with asyncio.timeout(SNAPSHOT_REQUEST_TIMEOUT_SECONDS):
                async with self._session.get(
                    self._url,
                    headers={"Authorization": "Bearer " + token,
                             "Accept": "application/json"},
                    allow_redirects=False,
                ) as response:
                    if response.status in (401, 403):
                        raise RuntimeAuthenticationFailed("Runtime snapshot unavailable")
                    if response.status != 200:
                        raise RuntimeUnavailable("Runtime snapshot unavailable")
                    if response.content_length is not None and response.content_length > 4096:
                        raise RuntimeUnavailable("Runtime snapshot unavailable")
                    body = await response.content.read(4097)
                    if len(body) > 4096:
                        raise RuntimeUnavailable("Runtime snapshot unavailable")
                    document = json.loads(body)
                    if not isinstance(document, dict):
                        raise ValueError("Invalid snapshot")
                    return document
        except RuntimeUnavailable:
            raise
        except Exception:
            raise RuntimeUnavailable("Runtime snapshot unavailable") from None

# Fixed Supervisor-internal App DNS name, not a user-supplied hostname or
# private IP. Private IPs and arbitrary App names could exfiltrate the token.
EXPECTED_APP_ENDPOINT = (
    "http://local-genvex-nabto-remote:18275/v1/snapshot"
)
EXPECTED_V3_APP_ENDPOINT = (
    "http://local-genvex-nabto-remote:18275/v3/snapshot"
)
EXPECTED_V4_APP_ENDPOINT = (
    "http://local-genvex-nabto-remote:18275/v4/snapshot"
)


def validate_private_endpoint(endpoint: str) -> None:
    """Pin bearer-token delivery to the dedicated Supervisor App endpoint."""
    if endpoint not in (EXPECTED_APP_ENDPOINT, EXPECTED_V3_APP_ENDPOINT,
                        EXPECTED_V4_APP_ENDPOINT):
        raise ValueError("Invalid internal runtime endpoint")
