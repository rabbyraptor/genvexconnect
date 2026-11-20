#!/usr/bin/env python3
"""Fake-only container-to-container snapshot transport smoke test.

Not called by the App entrypoint. No SDK or credentials. Intended exclusively
for a Docker --internal test network with no host port publication.
"""
from __future__ import annotations

from datetime import datetime, timezone
from http.client import HTTPConnection
import json
import sys

from polling_http_server import SnapshotHTTPServer

DEVICE = "123456789012"  # Fake test ID
TOKEN = "T" * 43  # Fake test token, NEVER use for a real installation
PORT = 18275


def serve(*, available: bool) -> None:
    def snapshot():
        if not available:
            return None
        return {
            "schema_version": 1,
            "device_id": DEVICE,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "health": "ok",
            "values": {
                "supply_air": 10.0, "outdoor_air": 3.0,
                "exhaust_air": 11.0, "extract_air": 9.0,
                "humidity": 55.0,
            },
        }

    service = SnapshotHTTPServer(
        bind_host="0.0.0.0", port=PORT, device_id=DEVICE,
        token=TOKEN, snapshot_provider=snapshot,
    )
    service.start()
    print("Fake-only HTTP server ready", flush=True)
    try:
        import threading
        threading.Event().wait()
    finally:
        service.stop()


def request(host: str, *, token: str | None):
    connection = HTTPConnection(host, PORT, timeout=4)
    try:
        headers = {"Accept": "application/json"}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        connection.request("GET", "/v1/snapshot", headers=headers)
        response = connection.getresponse()
        data = response.read(4097)
        if len(data) > 4096:
            raise RuntimeError("Oversized response")
        return response.status, json.loads(data)
    finally:
        connection.close()


def check(host: str, expected: str) -> None:
    status, body = request(host, token=None)
    assert status == 401 and body == {"error": "unauthorized"}
    status, body = request(host, token="X" * 43)
    assert status == 401 and body == {"error": "unauthorized"}
    status, body = request(host, token=TOKEN)
    if expected == "available":
        assert status == 200 and body["device_id"] == DEVICE
        assert body["values"]["humidity"] == 55.0
        assert set(body["values"]) == {
            "supply_air", "outdoor_air", "exhaust_air", "extract_air",
            "humidity",
        }
    else:
        assert status == 503 and body == {"error": "unavailable"}
    print("PASS: isolated container IPC " + expected, flush=True)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "serve":
        if sys.argv[2] not in ("available", "unavailable"):
            raise SystemExit(2)
        serve(available=sys.argv[2] == "available")
    elif len(sys.argv) == 4 and sys.argv[1] == "check":
        if sys.argv[3] not in ("available", "unavailable"):
            raise SystemExit(2)
        check(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(2)
