"""SDK-free contracts for one RPC45 -> short-lived private Core IPC."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
import ipc_core_live_once as live

DEVICE = "123456789012"
SETTINGS = {
    "device_id": DEVICE,
    "identity": "dummy@example.invalid",
    "unlock_secret": "not-a-real-secret",
    "ipc_token": "T" * 43,
}


def snapshot():
    return {
        "schema_version": 1, "device_id": DEVICE,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "health": "ok",
        "values": {
            "supply_air": 12.0, "outdoor_air": 3.0,
            "exhaust_air": 9.0, "extract_air": 10.0,
            "humidity": 55.0,
        },
    }


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_rpc_then_temporary_private_service(self):
        adapter = Mock(poll_once=AsyncMock(return_value=snapshot()))
        server = Mock()
        factory = Mock(return_value=server)
        states = []
        async def fake_sleep(seconds):
            self.assertEqual(seconds, live.SERVE_SECONDS)
            state = factory.call_args.kwargs["snapshot_provider"]()
            states.append(state)
            self.assertEqual(state["device_id"], DEVICE)
            self.assertEqual(state["values"]["humidity"], 55.0)
        with patch.object(live, "SDKSnapshotAdapter", return_value=adapter), \
             patch.object(live, "SnapshotHTTPServer", factory):
            await live.serve_once(SETTINGS, sleep=fake_sleep)
        adapter.poll_once.assert_awaited_once_with()
        self.assertEqual(factory.call_args.kwargs["bind_host"], "0.0.0.0")
        self.assertEqual(factory.call_args.kwargs["port"], 18275)
        self.assertEqual(factory.call_args.kwargs["token"], "T" * 43)
        server.start.assert_called_once_with()
        server.stop.assert_called_once_with()
        self.assertEqual(states[0], {})

    async def test_sdk_failure_never_binds_http(self):
        from sdk_snapshot_adapter import SDKSnapshotError
        adapter = Mock(poll_once=AsyncMock(
            side_effect=SDKSnapshotError("SDK_RPC45_FAILED")
        ))
        with patch.object(live, "SDKSnapshotAdapter", return_value=adapter), \
             patch.object(live, "SnapshotHTTPServer") as server:
            with self.assertRaises(SDKSnapshotError):
                await live.serve_once(SETTINGS, sleep=AsyncMock())
        server.assert_not_called()
        adapter.poll_once.assert_awaited_once_with()

    async def test_server_cleanup_on_cancellation(self):
        adapter = Mock(poll_once=AsyncMock(return_value=snapshot()))
        server = Mock()
        factory = Mock(return_value=server)
        state_list = []
        async def cancel(_):
            state_list.append(factory.call_args.kwargs["snapshot_provider"]())
            raise asyncio.CancelledError()
        with patch.object(live, "SDKSnapshotAdapter", return_value=adapter), \
             patch.object(live, "SnapshotHTTPServer", factory):
            with self.assertRaises(asyncio.CancelledError):
                await live.serve_once(SETTINGS, sleep=cancel)
        self.assertEqual(state_list[0], {})
        server.stop.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
