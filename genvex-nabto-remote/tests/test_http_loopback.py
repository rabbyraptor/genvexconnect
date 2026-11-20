"""Actual offline HTTP loopback tests for the bundled read-only runtime.

Only binds 127.0.0.1 on an ephemeral port, uses fake tokens/sensor values,
and never imports or starts the Nabto SDK or HA Core.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from polling_http_server import SnapshotHTTPServer


class LoopbackHTTPTests(unittest.TestCase):
    def setUp(self):
        self.device = "123456789012"
        self.token = "t" * 43
        self.snapshot = {
            "schema_version": 1,
            "device_id": self.device,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "health": "ok",
            "values": {
                "supply_air": 8.0, "outdoor_air": 3.0,
                "exhaust_air": 10.0, "extract_air": 9.0,
                "humidity": 55.0,
            },
        }
        self.server = SnapshotHTTPServer(
            bind_host="127.0.0.1", port=0,
            token=self.token, device_id=self.device,
            snapshot_provider=lambda: self.snapshot,
        )
        self.port = self.server._server.server_address[1]
        self.server.start()
        self.addCleanup(self.server.stop)

    def request(self, method="GET", path="/v1/snapshot", token=None,
                headers=None, body=None):
        headers = dict(headers or {})
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        client = HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            client.request(method, path, body=body, headers=headers)
            response = client.getresponse()
            payload = response.read(4097)
            return response.status, dict(response.getheaders()), payload
        finally:
            client.close()

    def test_authorized_snapshot(self):
        status, headers, payload = self.request(token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        document = json.loads(payload)
        self.assertEqual(document["device_id"], self.device)
        self.assertEqual(document["values"]["humidity"], 55.0)
        self.assertEqual(set(document), {
            "schema_version", "device_id", "timestamp_utc", "health", "values"
        })

    def test_wrong_and_missing_authentication(self):
        for token in (None, "w" * 43, "short"):
            with self.subTest(token_present=token is not None):
                status, _, payload = self.request(token=token)
                self.assertEqual(status, 401)
                self.assertEqual(json.loads(payload), {"error": "unauthorized"})

    def test_unavailable_does_not_return_stale_data(self):
        self.snapshot = None
        status, _, payload = self.request(token=self.token)
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(payload), {"error": "unavailable"})

    def test_stale_snapshot_unavailable(self):
        self.snapshot["timestamp_utc"] = (
            datetime.now(timezone.utc) - timedelta(minutes=4)
        ).isoformat()
        status, _, _ = self.request(token=self.token)
        self.assertEqual(status, 503)

    def test_unknown_routes_and_methods(self):
        # http.client automatically adds Content-Length: 0 for POST/PUT,
        # so the server intentionally returns 400 before route dispatch.
        for method, path, expected_status in (
            ("GET", "/debug", 404),
            ("GET", "/v1/snapshot?token=secret", 404),
            ("POST", "/v1/snapshot", 400),
            ("PUT", "/v1/snapshot", 400),
        ):
            with self.subTest(method=method, path=path):
                status, _, payload = self.request(
                    method=method, path=path, token=self.token
                )
                self.assertEqual(status, expected_status)
                self.assertNotIn(b"secret", payload)

    def test_unsupported_methods_without_body_headers_return_404(self):
        for method in ("POST", "PUT"):
            with self.subTest(method=method):
                client = HTTPConnection("127.0.0.1", self.port, timeout=3)
                try:
                    client.putrequest(method, "/v1/snapshot")
                    client.putheader("Authorization", "Bearer " + self.token)
                    client.endheaders()
                    response = client.getresponse()
                    self.assertEqual(response.status, 404)
                    self.assertEqual(
                        json.loads(response.read(4097)), {"error": "not_found"}
                    )
                finally:
                    client.close()

    def test_rejects_request_body_even_if_empty(self):
        status, _, payload = self.request(
            method="POST", token=self.token, headers={"Content-Length": "0"}
        )
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(payload), {"error": "bad_request"})

    def test_unauthorized_and_unknown_route_never_call_provider(self):
        calls = []
        def provider():
            calls.append("called")
            raise RuntimeError("SENSITIVE PROVIDER ERROR")
        # Swap the provider by starting a separate ephemeral server.
        server = SnapshotHTTPServer(
            bind_host="127.0.0.1", port=0, token=self.token,
            device_id=self.device, snapshot_provider=provider,
        )
        server.start()
        self.addCleanup(server.stop)
        old_port = self.port
        self.port = server._server.server_address[1]
        self.addCleanup(setattr, self, "port", old_port)
        for token, path, expected in (
            (None, "/v1/snapshot", 401),
            ("w" * 43, "/v1/snapshot", 401),
            (self.token, "/unknown", 404),
        ):
            status, _, payload = self.request(token=token, path=path)
            self.assertEqual(status, expected)
            self.assertNotIn(b"SENSITIVE", payload)
        self.assertEqual(calls, [])
        status, _, payload = self.request(token=self.token)
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(payload), {"error": "unavailable"})
        self.assertEqual(calls, ["called"])

    def test_arbitrary_interface_not_allowed(self):
        with self.assertRaises(ValueError):
            SnapshotHTTPServer(
                bind_host="192.0.2.1", port=18275,
                token=self.token, device_id=self.device,
                snapshot_provider=lambda: None,
            )


if __name__ == "__main__":
    unittest.main()
