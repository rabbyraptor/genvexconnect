"""Inert aiohttp IPC application factory for future private read-only App IPC.

No sockets are created, bound, exposed or started by importing this module or
calling build_ipc_application(). This is a source-only review candidate; it
MUST NOT be wired into the installed DEV2 App or a persistent polling service.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ipc_auth import IPCAuthError, authorize_read
from sensor_model import remote_hostname
from snapshot_api import handle_read_request


def create_handler(
    *, expected_token: str, device_id: str,
    get_snapshot: Callable[[], dict[str, Any] | None],
):
    """Create one bounded async HTTP handler, independent of network binding.

    Authenticate before touching the snapshot provider or exposing route
    status. Every reply is a fixed redacted JSON projection.
    """
    if (not isinstance(expected_token, str)
            or not expected_token.isascii()
            or not 40 <= len(expected_token) <= 128):
        raise ValueError("Invalid private IPC token")
    remote_hostname(device_id)
    if not callable(get_snapshot):
        raise ValueError("Invalid private snapshot provider")

    async def serve(request):
        from aiohttp import web

        auth = request.headers.get("Authorization")
        supplied = auth[len("Bearer "):] if isinstance(auth, str) and auth.startswith("Bearer ") else None
        try:
            authorize_read(expected_token, supplied)
        except IPCAuthError:
            return web.Response(status=401, body=b'{"error":"unauthorized"}',
                                content_type="application/json")

        # No other route or method may expose data, even when authenticated.
        if request.method != "GET" or request.raw_path != "/v1/snapshot":
            return web.Response(status=404, body=b'{"error":"not_found"}',
                                content_type="application/json")

        # Reject all request bodies (including chunked requests) to keep
        # this read-only endpoint free of hidden command payloads.
        if request.can_read_body or request.content_length not in (None, 0):
            return web.Response(status=413, body=b'{"error":"invalid_request"}',
                                content_type="application/json")

        try:
            snapshot = get_snapshot()
        except Exception:
            # Never echo internal error text or expose stale/partial readings.
            snapshot = None
        status, body = handle_read_request(
            method=request.method,
            path=request.raw_path,
            authorization=auth,
            expected_token=expected_token,
            device_id=device_id,
            snapshot=snapshot,
        )
        return web.Response(status=status, body=body,
                            content_type="application/json")

    return serve


def build_ipc_application(
    *, expected_token: str, device_id: str,
    get_snapshot: Callable[[], dict[str, Any] | None],
):
    """Build an unbound aiohttp Application; no network listener is launched."""
    from aiohttp import web

    app = web.Application(client_max_size=1024)
    app.router.add_route(
        "*", "/{tail:.*}",
        create_handler(expected_token=expected_token, device_id=device_id,
                       get_snapshot=get_snapshot),
    )
    return app
