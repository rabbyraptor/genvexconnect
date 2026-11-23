#!/usr/bin/env python3
"""Credential-free HAOS networking diagnostic; NEVER returns a real snapshot.

This server has a separate endpoint and a deliberately incompatible response
schema. It does not import Nabto, SDK adapters, polling or snapshot state.
It must only be launched after an explicit, validated App diagnostic opt-in.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json

DIAGNOSTIC_PATH = "/v1/diagnostic"
DIAGNOSTIC_BODY = json.dumps({
    "mode": "DIAGNOSTIC_ONLY",
    "synthetic": True,
    "notice": "NOT_REAL_SENSOR_DATA",
    "values": {
        "supply_air": 20.0,
        "outdoor_air": 5.0,
        "exhaust_air": 24.0,
        "extract_air": 22.0,
        "humidity": 50.0,
    },
}, separators=(",", ":")).encode("ascii")


class _DiagnosticHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 4
    allow_reuse_address = False


class DiagnosticHTTPServer:
    """Own a synthetic-only listener; production snapshot URLs always 404."""

    def __init__(self, *, bind_host: str, port: int):
        if bind_host not in ("127.0.0.1", "0.0.0.0"):
            raise ValueError("Invalid diagnostic bind host")
        if bind_host == "0.0.0.0" and port != 18275:
            raise ValueError("Diagnostic App listener must use port 18275")
        if type(port) is not int or not (
            1024 <= port <= 65535 or (port == 0 and bind_host == "127.0.0.1")
        ):
            raise ValueError("Invalid diagnostic port")

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def _reply(self, status: int, body: bytes):
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _handle(self):
                if (
                    self.headers.get("Transfer-Encoding") is not None
                    or self.headers.get("Content-Length") is not None
                ):
                    self._reply(400, b'{"error":"bad_request"}')
                elif self.command == "GET" and self.path == DIAGNOSTIC_PATH:
                    self._reply(200, DIAGNOSTIC_BODY)
                else:
                    self._reply(404, b'{"error":"not_found"}')

            def do_GET(self): self._handle()
            def do_POST(self): self._handle()
            def do_PUT(self): self._handle()
            def do_DELETE(self): self._handle()
            def do_HEAD(self): self._handle()
            def do_OPTIONS(self): self._handle()
            def log_message(self, *_args): pass

        self._server = _DiagnosticHTTPServer((bind_host, port), Handler)

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    def serve_forever(self) -> None:
        try:
            self._server.serve_forever(poll_interval=0.2)
        finally:
            self._server.server_close()

    def start(self):
        """Start explicitly from caller-controlled test harness only."""
        from threading import Thread
        self._thread = Thread(target=self._server.serve_forever,
                              kwargs={"poll_interval": 0.2}, daemon=True)
        self._thread.start()

    def stop(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=3)
