#!/usr/bin/env python3
"""One-shot live snapshot HTTP test server on a disposable Docker bridge.

Not production: never enrolls, polls or executes RPC. It reads an already
validated snapshot from a private tmpfs file. No device controls exist.
"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from snapshot_api import handle_read_request
from snapshot_contract import parse_snapshot


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--token-file", required=True, type=Path)
    p.add_argument("--snapshot-file", required=True, type=Path)
    p.add_argument("--port", type=int, default=18275)
    args = p.parse_args()
    if args.port != 18275:
        raise SystemExit("Unsupported IPC test port")
    token = args.token_file.read_text(encoding="ascii").strip()
    snapshot = json.loads(args.snapshot_file.read_bytes())
    device_id = snapshot["device_id"]
    # Check before binding; never expose invalid or incomplete raw diagnostics.
    parse_snapshot(snapshot, expected_device_id=device_id)

    class Handler(BaseHTTPRequestHandler):
        def _reply(self):
            status, payload = handle_read_request(
                method=self.command, path=self.path,
                authorization=self.headers.get("Authorization"),
                expected_token=token, device_id=device_id,
                snapshot=snapshot,
            )
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            self._reply()

        def do_POST(self):
            self._reply()

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print("PASS: one-shot live snapshot loaded and IPC fixture listening", flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
