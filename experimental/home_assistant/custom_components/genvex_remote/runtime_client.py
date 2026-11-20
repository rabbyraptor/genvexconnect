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
