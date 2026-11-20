"""Standalone experimental v2 HTTP bridge for loopback-only contract tests.

Never included in bundled HAOS runtime. The production v1 HTTP server
and its exact matching packaged source remain untouched. No Nabto calls,
socket or background task are created when this module is imported.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Callable

from snapshot_api import handle_read_request
from snapshot_api_v2 import V2_PATH, handle_v2_read_request


class _BoundedV2Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 4
    allow_reuse_address = False


class ExperimentalV2HTTPServer:
    """Explicitly opt-in, loopback-only test server with both versioned routes."""

    def __init__(
        self, *, bind_host: str, port: int, token: str,
        device_id: str, snapshot_provider: Callable[[], dict | None],
        v2_snapshot_provider: Callable[[], dict | None],
    ):
        if bind_host != "127.0.0.1" or type(port) is not int or not (
            port == 0 or 1024 <= port <= 65535
        ):
            raise ValueError("Experimental v2 bridge requires loopback-only bind")
        if not callable(snapshot_provider) or not callable(v2_snapshot_provider):
            raise ValueError("Both snapshot providers are required")
        self._thread = None
        self._server = None

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def _reply(self, status: int, payload: bytes) -> None:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def _handle(self):
                if self.headers.get("Transfer-Encoding") or self.headers.get("Content-Length"):
                    self._reply(400, b'{"error":"bad_request"}')
                    return
                request = dict(
                    method=self.command, path=self.path,
                    authorization=self.headers.get("Authorization"),
                    expected_token=token, device_id=device_id,
                )
                if self.path == V2_PATH:
                    handler, provider = handle_v2_read_request, v2_snapshot_provider
                else:
                    handler, provider = handle_read_request, snapshot_provider
                # The preflight invocation must reject missing token, incorrect
                # method and unexpected route WITHOUT consulting the provider.
                status, body = handler(**request, snapshot=None)
                if status != 503:
                    self._reply(status, body)
                    return
                try:
                    snapshot = provider()
                    status, body = handler(**request, snapshot=snapshot)
                except Exception:
                    status, body = 503, b'{"error":"unavailable"}'
                self._reply(status, body)

            def do_GET(self): self._handle()
            def do_POST(self): self._handle()
            def do_PUT(self): self._handle()
            def do_DELETE(self): self._handle()
            def log_message(self, *_args): pass

        self._server = _BoundedV2Server((bind_host, port), Handler)
        self._thread = Thread(
            target=self._server.serve_forever,
            kwargs={"poll_interval": 0.2},
            daemon=True,
        )

    def start(self):
        self._thread.start()

    def stop(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=3)
