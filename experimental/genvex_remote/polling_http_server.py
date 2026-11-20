"""Read-only, authenticated in-process HTTP bridge for an isolated runtime.

This module has no side effects on import. Bind only to a dedicated private
Docker/App network; NEVER publish this port on the host or internet.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Callable

from snapshot_api import handle_read_request


class _BoundedHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 4
    allow_reuse_address = False


class SnapshotHTTPServer:
    """Start/stop a minimal authenticated snapshot endpoint."""

    def __init__(self, *, bind_host: str, port: int, token: str,
                 device_id: str, snapshot_provider: Callable[[], dict | None]):
        if not bind_host or bind_host == "0.0.0.0" and port != 18275:
            raise ValueError("Invalid private bridge binding")
        if not isinstance(port, int) or not (1024 <= port <= 65535 or (port == 0 and bind_host == "127.0.0.1")):
            raise ValueError("Invalid bridge port")
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
                status, payload = handle_read_request(
                    method=self.command,
                    path=self.path,
                    authorization=self.headers.get("Authorization"),
                    expected_token=token,
                    device_id=device_id,
                    snapshot=snapshot_provider(),
                )
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
