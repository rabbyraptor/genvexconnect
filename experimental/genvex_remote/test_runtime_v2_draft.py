"""Offline loopback runtime end-to-end tests; fake RPC45, no SDK or accounts."""
from __future__ import annotations

import asyncio
import json
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ipc_auth import new_ipc_token
from runtime_v2_draft import ExperimentalV2Runtime
from v2_polling_state import ReadOnlyV2Poller


DEVICE = "123456789012"
RAW = (368, 308, 322, 378, 67, 6000, 5800)


class ExperimentalRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.calls = 0
        self.raw = RAW

        async def reader(_host, addresses):
            self.calls += 1
            self.assertEqual(addresses, (20, 21, 22, 23, 26, 18, 19))
            return self.raw

        self.reader = reader
        self.token = new_ipc_token()
        self.runtime = ExperimentalV2Runtime(
            device_id=DEVICE,
            adapter=ReadOnlyV2Poller(device_id=DEVICE, reader=reader),
            token=self.token,
            interval_seconds=60,
        )

    async def asyncTearDown(self):
        await self.runtime.stop()

    async def wait_for_poll(self):
        for _ in range(120):
            if self.runtime.state.current() is not None:
                return
            await asyncio.sleep(0.01)
        self.fail("Synthetic first poll did not complete")

    def fetch(self, route, *, token=None, method="GET"):
        port = self.runtime.local_port
        headers = {} if token is None else {
            "Authorization": "Bearer " + token
        }
        req = Request(
            f"http://127.0.0.1:{port}{route}",
            headers=headers, method=method,
        )
        try:
            with urlopen(req, timeout=3) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    async def test_construction_is_inert(self):
        self.assertIsNone(self.runtime.local_port)
        self.assertFalse(self.runtime.running)
        self.assertEqual(self.calls, 0)
        self.assertIsNone(self.runtime.state.current())

    async def test_both_versions_after_one_synthetic_rpc(self):
        await self.runtime.start()
        self.assertTrue(self.runtime.running)
        await self.wait_for_poll()
        self.assertEqual(self.calls, 1)
        status1, v1 = self.fetch("/v1/snapshot", token=self.token)
        status2, v2 = self.fetch("/v2/snapshot", token=self.token)
        self.assertEqual((status1, status2), (200, 200))
        self.assertEqual(self.calls, 1)
        self.assertEqual(v1["schema_version"], 1)
        self.assertEqual(v2["schema_version"], 2)
        self.assertEqual(v1["values"], v2["values"])
        self.assertNotIn("optional", v1)
        self.assertEqual(v2["optional"]["fan_duty"], {
            "fan_duty_supply": 60.0, "fan_duty_extract": 58.0
        })

    async def test_authentication_and_routes_cannot_trigger_rpc(self):
        await self.runtime.start()
        await self.wait_for_poll()
        self.assertEqual(self.fetch("/v1/snapshot")[0], 401)
        self.assertEqual(self.fetch("/v2/snapshot")[0], 401)
        self.assertEqual(
            self.fetch("/v2/snapshot", token=new_ipc_token())[0], 401
        )
        self.assertEqual(
            self.fetch("/debug", token=self.token)[0], 404
        )
        self.assertEqual(
            self.fetch("/v2/snapshot", token=self.token, method="DELETE")[0],
            404,
        )
        self.assertEqual(self.calls, 1)

    async def test_optional_fan_failure_preserves_five_values(self):
        self.raw = RAW[:5] + (10001, 5800)
        await self.runtime.start()
        await self.wait_for_poll()
        _, v2 = self.fetch("/v2/snapshot", token=self.token)
        self.assertEqual(v2["optional"]["fan_duty"], {})
        _, v1 = self.fetch("/v1/snapshot", token=self.token)
        self.assertEqual(v1["values"]["supply_air"], 6.8)

    async def test_failed_followup_marks_both_unavailable_then_recovers(self):
        await self.runtime.start()
        await self.wait_for_poll()
        self.raw = RAW[:4]
        self.assertFalse(await self.runtime.state.refresh())
        for route in ("/v1/snapshot", "/v2/snapshot"):
            self.assertEqual(self.fetch(route, token=self.token)[0], 503)
        self.raw = RAW
        self.assertTrue(await self.runtime.state.refresh())
        self.assertEqual(
            self.fetch("/v2/snapshot", token=self.token)[0], 200
        )
        self.assertEqual(self.calls, 3)

    async def test_stop_invalidates_snapshot_and_closes_listener(self):
        await self.runtime.start()
        await self.wait_for_poll()
        await self.runtime.stop()
        self.assertFalse(self.runtime.running)
        self.assertIsNone(self.runtime.local_port)
        self.assertIsNone(self.runtime.state.current())
        await self.runtime.start()
        await self.wait_for_poll()
        self.assertEqual(self.calls, 2)

    async def test_double_start_and_invalid_config(self):
        await self.runtime.start()
        with self.assertRaises(RuntimeError):
            await self.runtime.start()
        with self.assertRaises(ValueError):
            ExperimentalV2Runtime(
                device_id="000000000000",
                adapter=ReadOnlyV2Poller(device_id=DEVICE, reader=self.reader),
                token=self.token,
            )
        with self.assertRaises(ValueError):
            ExperimentalV2Runtime(
                device_id=DEVICE,
                adapter=ReadOnlyV2Poller(device_id=DEVICE, reader=self.reader),
                token="bad",
            )
        with self.assertRaises(ValueError):
            ExperimentalV2Runtime(
                device_id=DEVICE,
                adapter=ReadOnlyV2Poller(device_id=DEVICE, reader=self.reader),
                token=self.token, port=80,
            )


if __name__ == "__main__":
    unittest.main()
