"""Read-only, authenticated in-process HTTP bridge for an isolated runtime.

This module has no side effects on import. Bind only to a dedicated private
Docker/App network; NEVER publish this port on the host or internet.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Callable

from snapshot_api import handle_read_request
from snapshot_api_v3 import V3_PATH, handle_v3_read_request
from snapshot_api_v4 import V4_PATH, handle_v4_read_request


class _BoundedHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 4
    allow_reuse_address = False


class SnapshotHTTPServer:
    """Start/stop a minimal authenticated snapshot endpoint."""

    def __init__(self, *, bind_host: str, port: int, token: str,
                 device_id: str, snapshot_provider: Callable[[], dict | None],
                 v3_snapshot_provider: Callable[[], dict | None] | None = None,
                 v4_snapshot_provider: Callable[[], dict | None] | None = None):
        if bind_host not in ("127.0.0.1", "0.0.0.0"):
            raise ValueError("Invalid private bridge binding")
        if bind_host == "0.0.0.0" and port != 18275:
            raise ValueError("Only the fixed internal port may bind on container interfaces")
        if not isinstance(port, int) or not (1024 <= port <= 65535 or (port == 0 and bind_host == "127.0.0.1")):
            raise ValueError("Invalid bridge port")
        if v3_snapshot_provider is not None and not callable(v3_snapshot_provider):
            raise ValueError("Invalid v3 provider")
        if v4_snapshot_provider is not None and not callable(v4_snapshot_provider):
            raise ValueError("Invalid v4 provider")
        self._thread = None
        self._server = None

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def _json_reply(self, status: int, payload: bytes) -> None:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def _handle(self):
                # This is a body-free read-only API. Reject any request body
                # without leaking HTML from BaseHTTPRequestHandler.send_error.
                if self.headers.get("Transfer-Encoding") or self.headers.get("Content-Length"):
                    self._json_reply(400, b'{"error":"bad_request"}')
                    return
                # Authorize and validate the route before consulting the
                # snapshot provider. Unauthorized or unknown requests must
                # never invoke it (or expose provider exceptions).
                request = dict(
                    method=self.command,
                    path=self.path,
                    authorization=self.headers.get("Authorization"),
                    expected_token=token,
                    device_id=device_id,
                )
                if self.path == V4_PATH and v4_snapshot_provider is not None:
                    handler, provider = handle_v4_read_request, v4_snapshot_provider
                elif self.path == V3_PATH and v3_snapshot_provider is not None:
                    handler, provider = handle_v3_read_request, v3_snapshot_provider
                else:
                    handler, provider = handle_read_request, snapshot_provider
                status, payload = handler(**request, snapshot=None)
                if status != 503:
                    self._json_reply(status, payload)
                    return
                try:
                    snapshot = provider()
                    status, payload = handler(**request, snapshot=snapshot)
                except Exception:
                    self._json_reply(503, b'{"error":"unavailable"}')
                    return
                self._json_reply(status, payload)

            def do_GET(self): self._handle()
            def do_POST(self): self._handle()
            def do_PUT(self): self._handle()
            def do_DELETE(self): self._handle()
            def log_message(self, *_args): pass

        self._server = _BoundedHTTPServer((bind_host, port), Handler)
        self._thread = Thread(target=self._server.serve_forever,
                              kwargs={"poll_interval": 0.2}, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=3)
