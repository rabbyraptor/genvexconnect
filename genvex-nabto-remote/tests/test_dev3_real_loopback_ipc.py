"""Real local TCP loopback test of the existing DEV3 private IPC listener.

The listener binds exclusively to 127.0.0.1 on an ephemeral port in
the isolated GitHub runner. It never starts the Nabto SDK, HAOS, polling,
an internet-facing socket or a device connection.
"""
from __future__ import annotations

from datetime import datetime, timezone
import http.client
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))

from polling_http_server import SnapshotHTTPServer

DEVICE = "123456789012"
TOKEN = "L" * 48


def valid_snapshot():
    return {
        "schema_version": 1,
        "device_id": DEVICE,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "health": "ok",
        "values": {
            "supply_air": 6.7, "outdoor_air": 0.2,
            "exhaust_air": 1.8, "extract_air": 7.8,
            "humidity": 66.0,
        },
    }


class RealLoopbackTests(unittest.TestCase):
    def setUp(self):
        self.calls = 0
        self.snapshot = valid_snapshot()

        def supplier():
            self.calls += 1
            return self.snapshot

        self.server = SnapshotHTTPServer(
            bind_host="127.0.0.1", port=0, token=TOKEN,
            device_id=DEVICE, snapshot_provider=supplier,
        )
        self.port = self.server._server.server_address[1]
        self.server.start()

    def tearDown(self):
        self.server.stop()

    def request(self, method="GET", path="/v1/snapshot", *,
                token=TOKEN, body=None, extra_headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        headers = dict(extra_headers or {})
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            data = response.read(4097)
            return response.status, data, dict(response.getheaders())
        finally:
            connection.close()

    def test_success_requires_exact_token_and_valid_readings(self):
        status, body, headers = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["values"]["humidity"], 66.0)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(self.calls, 1)

    def test_bad_token_and_unknown_paths_never_hit_snapshot(self):
        for token in (None, "X" * 48, "short"):
            status, body, _ = self.request(token=token)
            self.assertEqual(status, 401)
            self.assertEqual(body, b'{"error":"unauthorized"}')
        for method, path in (("POST", "/v1/snapshot"),
                             ("GET", "/v1/snapshot?debug=1"),
                             ("GET", "/v1/private")):
            status, body, _ = self.request(method, path)
            self.assertEqual(status, 404)
            self.assertEqual(body, b'{"error":"not_found"}')
        self.assertEqual(self.calls, 0)

    def test_bad_request_body_rejected_before_read(self):
        status, body, _ = self.request(
            "POST", "/v1/snapshot", body=b"hidden-command"
        )
        self.assertEqual(status, 400)
        self.assertEqual(body, b'{"error":"bad_request"}')
        self.assertEqual(self.calls, 0)

    def test_missing_and_wrong_device_snapshots_are_unavailable(self):
        self.snapshot = None
        status, body, _ = self.request()
        self.assertEqual((status, body), (503, b'{"error":"unavailable"}'))
        invalid = valid_snapshot()
        invalid["device_id"] = "999999999999"
        self.snapshot = invalid
        status, body, _ = self.request()
        self.assertEqual((status, body), (503, b'{"error":"unavailable"}'))
        self.assertEqual(self.calls, 2)

    def test_recovery_after_unavailable_snapshot(self):
        self.snapshot = None
        self.assertEqual(self.request()[0], 503)
        self.snapshot = valid_snapshot()
        self.assertEqual(self.request()[0], 200)
        self.assertEqual(self.calls, 2)


if __name__ == "__main__":
    unittest.main()
