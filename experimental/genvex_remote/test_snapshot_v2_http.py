"""Offline HTTP integration tests for the opt-in v2 endpoint.

Uses loopback with synthetic data only. No Nabto SDK, HA, vendor account,
live device, external network or HAOS App changes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ipc_auth import new_ipc_token
from polling_http_server import SnapshotHTTPServer
from snapshot_v2_draft import make_v2_from_v1


class V2HTTPTests(unittest.TestCase):
    def setUp(self):
        self.device = "123456789012"
        self.token = new_ipc_token()
        self.v1 = {
            "schema_version": 1, "device_id": self.device,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "health": "ok",
            "values": {
                "supply_air": 6.7, "outdoor_air": 0.4, "exhaust_air": 1.8,
                "extract_air": 7.8, "humidity": 67.0,
            },
        }
        self.fan_raw = (6000, 5800)
        self.calls = {"v1": 0, "v2": 0}

    def v1_provider(self):
        self.calls["v1"] += 1
        return self.v1

    def v2_provider(self):
        self.calls["v2"] += 1
        return make_v2_from_v1(
            self.v1, expected_device_id=self.device, fan_raw=self.fan_raw
        )

    def serve(self, *, opt_in):
        server = SnapshotHTTPServer(
            bind_host="127.0.0.1", port=0, token=self.token,
            device_id=self.device, snapshot_provider=self.v1_provider,
            v2_snapshot_provider=self.v2_provider if opt_in else None,
        )
        server.start()
        self.addCleanup(server.stop)
        return server._server.server_port

    def fetch(self, port, *, path="/v2/snapshot", token=None, method="GET", data=None):
        headers = {} if token is None else {"Authorization": "Bearer " + token}
        request = Request(f"http://127.0.0.1:{port}{path}",
                          headers=headers, method=method, data=data)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_v2_disabled_by_default_and_v1_unchanged(self):
        port = self.serve(opt_in=False)
        self.assertEqual(self.fetch(port, path="/v2/snapshot", token=self.token)[0], 404)
        self.assertEqual(self.calls, {"v1": 0, "v2": 0})
        status, body = self.fetch(port, path="/v1/snapshot", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(body["schema_version"], 1)
        self.assertEqual(body["values"]["humidity"], 67.0)
        self.assertEqual(self.calls, {"v1": 1, "v2": 0})

    def test_opted_in_v2_and_original_v1_alongside(self):
        port = self.serve(opt_in=True)
        status, body = self.fetch(port, token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(body["schema_version"], 2)
        self.assertEqual(body["optional"]["fan_duty"], {
            "fan_duty_supply": 60.0, "fan_duty_extract": 58.0,
        })
        self.assertEqual(body["values"]["humidity"], 67.0)
        self.assertEqual(self.calls, {"v1": 0, "v2": 1})
        status, body = self.fetch(port, path="/v1/snapshot", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(body["schema_version"], 1)

    def test_v2_authentication_precedes_provider_and_route(self):
        port = self.serve(opt_in=True)
        self.assertEqual(self.fetch(port)[0], 401)
        self.assertEqual(self.fetch(port, token=new_ipc_token())[0], 401)
        self.assertEqual(self.fetch(port, token=self.token, path="/v2/secret")[0], 404)
        self.assertEqual(self.fetch(port, token=self.token, method="DELETE")[0], 404)
        self.assertEqual(self.calls, {"v1": 0, "v2": 0})

    def test_optional_failure_degrades_without_fake_zero(self):
        port = self.serve(opt_in=True)
        self.fan_raw = (6000,)
        status, body = self.fetch(port, token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(body["optional"]["fan_duty"], {})
        self.assertEqual(body["values"]["supply_air"], 6.7)
        self.fan_raw = (0, 0)
        status, body = self.fetch(port, token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(body["optional"]["fan_duty"],
                         {"fan_duty_supply": 0.0, "fan_duty_extract": 0.0})

    def test_stale_base_and_wrong_device_unavailable(self):
        port = self.serve(opt_in=True)
        self.v1["timestamp_utc"] = (
            datetime.now(timezone.utc) - timedelta(minutes=5)
        ).isoformat()
        status, body = self.fetch(port, token=self.token)
        self.assertEqual((status, body), (503, {"error": "unavailable"}))
        self.v1["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
        self.v1["device_id"] = "000000000000"
        status, body = self.fetch(port, token=self.token)
        self.assertEqual((status, body), (503, {"error": "unavailable"}))

    def test_post_body_rejected_before_provider(self):
        port = self.serve(opt_in=True)
        status, body = self.fetch(
            port, token=self.token, method="POST", data=b"private-payload"
        )
        self.assertEqual((status, body), (400, {"error": "bad_request"}))
        self.assertEqual(self.calls, {"v1": 0, "v2": 0})


if __name__ == "__main__":
    unittest.main()
