"""Narrow authentication primitive for a future internal App-to-HA bridge.

No network listener is exposed. The secret must be generated and provisioned
over a separately trusted channel; do not publish it in logs or App options.
"""
from __future__ import annotations

import hmac
import secrets


class IPCAuthError(Exception):
    """Authentication failed; do not disclose details."""


def new_ipc_token() -> str:
    """Generate an opaque 256-bit transport credential."""
    return secrets.token_urlsafe(32)


def authorize_read(expected: str, supplied: str | None) -> None:
    """Fail closed and use constant-time comparison on valid-format tokens."""
    if not isinstance(expected, str) or not isinstance(supplied, str):
        raise IPCAuthError("Unauthorized runtime request")
    if not (40 <= len(expected) <= 128 and 40 <= len(supplied) <= 128):
        raise IPCAuthError("Unauthorized runtime request")
    if not (expected.isascii() and supplied.isascii()):
        raise IPCAuthError("Unauthorized runtime request")
    if not hmac.compare_digest(expected.encode("ascii"), supplied.encode("ascii")):
        raise IPCAuthError("Unauthorized runtime request")
