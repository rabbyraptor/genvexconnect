"""SDK-free DEV3 integration regression: polling -> private HTTP -> fail/recover.

Uses the real PollingService, SnapshotState and SnapshotHTTPServer on
127.0.0.1 with a synthetic injected poller. No Nabto device, HAOS,
credentials, external socket or Home Assistant installation is involved.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import http.client
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))

from polling_http_server import SnapshotHTTPServer
from polling_service import PollingService
from snapshot_state import SnapshotState

DEVICE = "123456789012"
TOKEN = "T" * 48
VALUES = {
    "supply_air": 7.3,
    "outdoor_air": 4.2,
    "exhaust_air": 4.8,
    "extract_air": 7.7,
    "humidity": 68.0,
}


def snapshot(*, supply=7.3):
    values = dict(VALUES)
    values["supply_air"] = supply
    return {
        "schema_version": 1,
        "device_id": DEVICE,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "health": "ok",
        "values": values,
    }


class SequencePoller:
    device_id = DEVICE

    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = 0

    async def poll_once(self):
        self.calls += 1
        result = next(self.outcomes)
        if isinstance(result, BaseException):
            raise result
        return result


class RealPollingHTTPRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.poller = SequencePoller([
            snapshot(), RuntimeError("synthetic RPC failure"),
            snapshot(supply=7.1),
        ])
        self.state = SnapshotState(self.poller)
        self.results = asyncio.Queue()
        async def on_result(ok):
            await self.results.put(ok)

        self.service = PollingService(
            self.state, interval_seconds=1, on_result=on_result
        )
        self.server = SnapshotHTTPServer(
            bind_host="127.0.0.1",
            port=0,
            token=TOKEN,
            device_id=DEVICE,
            snapshot_provider=self.state.current,
        )
        self.port = self.server._server.server_address[1]
        self.server.start()

    async def asyncTearDown(self):
        await self.service.stop()
        await asyncio.to_thread(self.server.stop)

    def request(self, *, authorized=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        headers = {"Accept": "application/json"}
        if authorized:
            headers["Authorization"] = "Bearer " + TOKEN
        try:
            conn.request("GET", "/v1/snapshot", headers=headers)
            response = conn.getresponse()
            raw = response.read(4097)
            self.assertLessEqual(len(raw), 4096)
            return response.status, json.loads(raw)
        finally:
            conn.close()

    async def await_result(self, expected):
        outcome = await asyncio.wait_for(self.results.get(), timeout=4)
        self.assertIs(outcome, expected)

    async def test_real_service_http_failure_and_automatic_recovery(self):
        # The production lifecycle schedules all three reads. The test never
        # manually refreshes SnapshotState or substitutes an HTTP handler.
        await self.service.start()
        await self.await_result(True)
        status, first = await asyncio.to_thread(self.request)
        self.assertEqual(status, 200)
        self.assertEqual(first["values"], VALUES)
        self.assertEqual(first["health"], "ok")
        self.assertIsNotNone(datetime.fromisoformat(
            first["timestamp_utc"].replace("Z", "+00:00")
        ).tzinfo)

        # An unauthorized request cannot read even a valid snapshot.
        status, body = await asyncio.to_thread(self.request, authorized=False)
        self.assertEqual((status, body), (401, {"error": "unauthorized"}))

        await self.await_result(False)
        status, body = await asyncio.to_thread(self.request)
        self.assertEqual((status, body), (503, {"error": "unavailable"}))
        self.assertIsNone(self.state.current())

        # Without a service restart, the next scheduled attempt restores one
        # *new* complete five-value batch; the old batch is never served.
        await self.await_result(True)
        status, recovered = await asyncio.to_thread(self.request)
        self.assertEqual(status, 200)
        self.assertEqual(set(recovered["values"]), set(VALUES))
        self.assertEqual(recovered["values"]["supply_air"], 7.1)
        self.assertNotEqual(recovered["values"], first["values"])
        self.assertEqual(self.poller.calls, 3)
        self.assertEqual(self.state.generation, 3)
        self.assertTrue(self.service.running)

        await self.service.stop()
        status, body = await asyncio.to_thread(self.request)
        self.assertEqual((status, body), (503, {"error": "unavailable"}))


if __name__ == "__main__":
    unittest.main()
