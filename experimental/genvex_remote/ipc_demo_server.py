#!/usr/bin/env python3
"""Disposable two-container HTTP transport smoke test, NEVER production API.

Uses fake sensor values and an ephemeral file-supplied token. The endpoint
exposes NO real account, Nabto SDK operations, enrollment or device controls.
Run only on a dedicated disposable internal Docker bridge, never on the HAOS
host network. No service/process is started by importing this module.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from snapshot_api import handle_read_request

_FAKE_DEVICE = "123456789012"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    args = parser.parse_args()
    # A dedicated Docker network is the responsibility of the test harness.
    # This process must never be packaged in the installed runtime App.
    if not 1024 <= args.port <= 65535:
        raise SystemExit("Invalid test port")
    token = args.token_file.read_text(encoding="ascii").strip()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, payload: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _handle(self) -> None:
            # Always use the fake data, never use or import Nabto credentials.
            snapshot = {
                "schema_version": 1,
                "device_id": _FAKE_DEVICE,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "health": "ok",
                "values": {
                    "supply_air": 6.7, "outdoor_air": -0.1,
                    "exhaust_air": 1.5, "extract_air": 7.7,
                    "humidity": 65,
                },
            }
            code, result = handle_read_request(
                method=self.command, path=self.path,
                authorization=self.headers.get("Authorization"),
                expected_token=token, device_id=_FAKE_DEVICE,
                snapshot=snapshot,
            )
            self._send(code, result)

        def do_GET(self) -> None:
            self._handle()

        def do_POST(self) -> None:
            # Never read POST data or perform any registration.
            self._handle()

        def log_message(self, _format: str, *args: object) -> None:
            # Headers, tokens, and even query strings must not be logged.
            return

    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    print("Test-only snapshot IPC service listening; no Nabto SDK is loaded", flush=True)
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
