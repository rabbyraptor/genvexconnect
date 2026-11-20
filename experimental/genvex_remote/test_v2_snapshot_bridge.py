"""Offline v2->v1/v2 read-only HTTP test with one injected fake RPC."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ipc_auth import new_ipc_token
from v2_polling_state import ReadOnlyV2Poller, V2SnapshotState
from v2_snapshot_bridge import OptInV2SnapshotBridge

DEVICE = "123456789012"
RAW = (368, 308, 322, 378, 67, 6000, 5800)


class V2SnapshotBridgeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.token = new_ipc_token()
        self.calls = 0
        self.raw = RAW

        async def read(host, addresses):
            self.calls += 1
            self.assertEqual(host, DEVICE + ".remote.lscontrol.dk")
            self.assertEqual(addresses, (20, 21, 22, 23, 26, 18, 19))
            return self.raw

        self.state = V2SnapshotState(
            ReadOnlyV2Poller(device_id=DEVICE, reader=read)
        )
        self.bridge = OptInV2SnapshotBridge(
            state=self.state, device_id=DEVICE
        )
        self.server = self.bridge.new_loopback_server(token=self.token)
        self.port = self.server._server.server_port
        self.server.start()
        self.addCleanup(self.server.stop)

    def request(self, path, *, token=None, method="GET"):
        headers = {} if token is None else {
            "Authorization": "Bearer " + token
        }
        req = Request(
            f"http://127.0.0.1:{self.port}{path}",
            headers=headers, method=method
        )
        try:
            with urlopen(req, timeout=3) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    async def test_no_snapshot_before_first_poll(self):
        self.assertEqual(
            self.request("/v1/snapshot", token=self.token),
            (503, {"error": "unavailable"}),
        )
        self.assertEqual(
            self.request("/v2/snapshot", token=self.token),
            (503, {"error": "unavailable"}),
        )
        self.assertEqual(self.calls, 0)

    async def test_one_rpc_serves_both_versions(self):
        self.assertTrue(await self.state.refresh())
        self.assertEqual(self.calls, 1)
        status_v1, v1 = self.request("/v1/snapshot", token=self.token)
        status_v2, v2 = self.request("/v2/snapshot", token=self.token)
        self.assertEqual((status_v1, status_v2), (200, 200))
        self.assertEqual(self.calls, 1)
        self.assertEqual(v1["schema_version"], 1)
        self.assertEqual(v2["schema_version"], 2)
        self.assertEqual(v1["timestamp_utc"], v2["timestamp_utc"])
        self.assertEqual(v1["values"], v2["values"])
        self.assertNotIn("optional", v1)
        self.assertEqual(v1["values"]["supply_air"], 6.8)
        self.assertEqual(v2["optional"]["fan_duty"], {
            "fan_duty_supply": 60.0, "fan_duty_extract": 58.0
        })

    async def test_auth_and_no_writes(self):
        self.assertTrue(await self.state.refresh())
        self.assertEqual(self.request("/v2/snapshot")[0], 401)
        self.assertEqual(
            self.request("/v1/snapshot", token=new_ipc_token())[0], 401
        )
        self.assertEqual(
            self.request("/v2/snapshot", token=self.token, method="DELETE")[0],
            404,
        )
        self.assertEqual(
            self.request("/debug", token=self.token)[0], 404
        )
        self.assertEqual(self.calls, 1)

    async def test_invalid_fan_pair_degrades_without_zero(self):
        self.raw = RAW[:5] + (10001, 5800)
        self.assertTrue(await self.state.refresh())
        status, v2 = self.request("/v2/snapshot", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(v2["optional"]["fan_duty"], {})
        self.assertEqual(
            self.request("/v1/snapshot", token=self.token)[0], 200
        )

    async def test_failed_followup_clears_both_routes(self):
        self.assertTrue(await self.state.refresh())
        self.raw = RAW[:4]
        self.assertFalse(await self.state.refresh())
        for path in ("/v1/snapshot", "/v2/snapshot"):
            self.assertEqual(
                self.request(path, token=self.token)[0], 503
            )
        self.raw = RAW
        self.assertTrue(await self.state.refresh())
        self.assertEqual(
            self.request("/v2/snapshot", token=self.token)[0], 200
        )
        self.assertEqual(self.calls, 3)

    async def test_stale_data_clears_both_routes(self):
        self.assertTrue(await self.state.refresh())
        self.state._snapshot["timestamp_utc"] = (
            datetime.now(timezone.utc) - timedelta(minutes=5)
        ).isoformat()
        for path in ("/v1/snapshot", "/v2/snapshot"):
            self.assertEqual(
                self.request(path, token=self.token)[0], 503
            )

    def test_reject_mismatched_state_device_and_external_bind(self):
        with self.assertRaises(ValueError):
            OptInV2SnapshotBridge(
                state=self.state, device_id="000000000000"
            )
        with self.assertRaises(ValueError):
            self.bridge.new_loopback_server(token=self.token, port=80)


if __name__ == "__main__":
    unittest.main()
