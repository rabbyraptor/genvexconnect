"""DEV8.4.1 cross-boundary fake App -> real HTTP -> HA reader/coordinator.

The external SDK and Supervisor are replaced by fixtures. HTTP uses only
a local ephemeral 127.0.0.1 server and cannot contact any gateway.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from test_snapshot import HERE  # Import-free HA component fixture namespace.
from test_freshness import load_coordinator
from dev_remote.runtime_client import (
    AuthenticatedSnapshotReader, EXPECTED_V3_APP_ENDPOINT,
)

APP = Path(__file__).resolve().parents[3] / "genvex-nabto-remote" / "runtime"
sys.path.insert(0, str(APP))
from raw_registers_v3 import make_raw_v3
from raw_snapshot_state_v3 import RawV3SnapshotState
from polling_http_server import SnapshotHTTPServer

DEVICE = "123456789012"
OLD = "Q" * 43
NEW = "R" * 43


class _FixtureWorker:
    device_id = DEVICE

    def __init__(self):
        self.extra = (0, 6000, 5800, 2432, 2268, 0, 0, 0, 0, 0, 0, 10)
        self.polls = 0

    async def poll_once(self):
        self.polls += 1
        return make_raw_v3(
            device_id=DEVICE,
            measured_at=datetime.now(timezone.utc),
            baseline_raw=(368, 308, 322, 378, 67),
            additional_raw=self.extra,
        )


class _AsyncResponse:
    def __init__(self, status, raw):
        self.status = status
        self.content_length = len(raw)

        class _Content:
            async def read(self, limit):
                return raw[:limit]

        self.content = _Content()


def _real_loopback_get(port, path, authorization):
    request = Request(
        f"http://127.0.0.1:{port}{path}",
        headers={
            "Authorization": authorization,
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=3) as response:
            return response.status, response.read(4097)
    except HTTPError as error:
        return error.code, error.read(4097)


class _Context:
    def __init__(self, port_provider, path, auth):
        self._port_provider = port_provider
        self._path = path
        self._auth = auth

    async def __aenter__(self):
        status, body = await asyncio.to_thread(
            _real_loopback_get,
            self._port_provider(), self._path, self._auth,
        )
        return _AsyncResponse(status, body)

    async def __aexit__(self, *_args):
        return None


class _Session:
    def __init__(self, port_provider):
        self._port_provider = port_provider
        self.requests = []

    def get(self, url, *, headers, allow_redirects):
        assert url == EXPECTED_V3_APP_ENDPOINT
        assert allow_redirects is False
        auth = headers["Authorization"]
        self.requests.append(auth)
        return _Context(self._port_provider, urlsplit(url).path, auth)


class CombinedCoreRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.worker = _FixtureWorker()
        self.state = RawV3SnapshotState(self.worker)
        self.server = None
        self.port = None
        self.start_server(OLD)
        self.session = _Session(lambda: self.port)

    def start_server(self, token):
        self.server = SnapshotHTTPServer(
            bind_host="127.0.0.1",
            port=0, token=token, device_id=DEVICE,
            snapshot_provider=self.state.current,
            v3_snapshot_provider=self.state.current_v3,
        )
        self.port = self.server._server.server_port
        self.server.start()

    async def rotate_server(self, new_token):
        await asyncio.to_thread(self.server.stop)
        self.start_server(new_token)

    async def asyncTearDown(self):
        if self.server is not None:
            await asyncio.to_thread(self.server.stop)

    async def test_live_http_401_refresh_then_seventeen_raw_values(self):
        self.assertTrue(await self.state.refresh())
        calls = []

        async def loader():
            calls.append("lookup")
            return NEW

        reader = AuthenticatedSnapshotReader(
            self.session,
            endpoint=EXPECTED_V3_APP_ENDPOINT,
            token=OLD, token_loader=loader,
        )
        coord = load_coordinator()(
            None, DEVICE, reader, raw_registers_v3=True,
        )
        first = await coord._async_update_data()
        self.assertEqual(first["supply_air"], 6.8)
        self.assertEqual(first["raw_supply_air"], 368)
        self.assertEqual(first["raw_fan_duty_supply"], 6000)
        self.assertEqual(len(first), 22)
        self.assertEqual(calls, [])
        self.assertEqual(self.worker.polls, 1)

        await self.rotate_server(NEW)
        self.assertTrue(await self.state.refresh())
        after_rotation = await coord._async_update_data()
        self.assertEqual(after_rotation["raw_fan_duty_supply"], 6000)
        self.assertEqual(calls, ["lookup"])
        self.assertEqual(
            self.session.requests[-2:],
            ["Bearer " + OLD, "Bearer " + NEW],
        )
        # The HTTP reader never schedules a new RPC poll itself.
        self.assertEqual(self.worker.polls, 2)

        self.worker.extra = None
        self.assertTrue(await self.state.refresh())
        missing = await coord._async_update_data()
        self.assertEqual(missing["humidity"], 67.0)
        self.assertEqual(missing["raw_humidity"], 67)
        self.assertNotIn("raw_fan_duty_supply", missing)
        self.assertEqual(len(missing), 10)
        self.assertEqual(calls, ["lookup"])

    async def test_503_never_refreshes_supervisor_token(self):
        calls = []

        async def loader():
            calls.append("not-allowed")
            return NEW

        reader = AuthenticatedSnapshotReader(
            self.session, endpoint=EXPECTED_V3_APP_ENDPOINT,
            token=OLD, token_loader=loader,
        )
        coord = load_coordinator()(None, DEVICE, reader, raw_registers_v3=True)
        from test_freshness import UpdateFailed
        with self.assertRaises(UpdateFailed):
            await coord._async_update_data()
        self.assertEqual(calls, [])
        self.assertTrue(await self.state.refresh())
        self.assertEqual((await coord._async_update_data())["raw_rotor_rpm"], 10)

    async def test_failed_supervisor_lookup_keeps_last_valid_measurement(self):
        self.assertTrue(await self.state.refresh())
        calls = []

        async def loader():
            calls.append("failure")
            raise RuntimeError("NEVER_LOG_PRIVATE_SUPERVISOR_VALUE")

        reader = AuthenticatedSnapshotReader(
            self.session, endpoint=EXPECTED_V3_APP_ENDPOINT,
            token=OLD, token_loader=loader,
        )
        coord = load_coordinator()(None, DEVICE, reader, raw_registers_v3=True)
        first = await coord._async_update_data()
        await self.rotate_server(NEW)
        cached = await coord._async_update_data()
        self.assertEqual(first, cached)
        self.assertEqual(calls, ["failure"])
        self.assertEqual(reader._token, OLD)


if __name__ == "__main__":
    unittest.main()
