"""SDK-free tests for the one-RPC private-container IPC probe."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
import ipc_once

DEVICE = "123456789012"
SETTINGS = {"device_id": DEVICE, "identity": "private@example.invalid",
            "unlock_secret": "never-logged"}


def fresh_snapshot():
    return {
        "schema_version": 1, "device_id": DEVICE,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "health": "ok", "values": {
            "supply_air": 6.7, "outdoor_air": 0.2,
            "exhaust_air": 1.8, "extract_air": 7.8, "humidity": 66.0,
        },
    }


class SmokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_exactly_one_rpc45_and_one_local_check(self):
        adapter = Mock(poll_once=AsyncMock(return_value=fresh_snapshot()))
        server = Mock()
        server._server.server_address = ("127.0.0.1", 27800)
        async def fake_to_thread(func, port, token, state):
            self.assertEqual(port, 27800)
            self.assertEqual(state["values"]["humidity"], 66.0)
            self.assertTrue(40 <= len(token) <= 128)
            state.clear()
        with patch.object(ipc_once, "SDKSnapshotAdapter", return_value=adapter), \
             patch.object(ipc_once, "SnapshotHTTPServer", return_value=server), \
             patch.object(ipc_once.asyncio, "to_thread", side_effect=fake_to_thread):
            await ipc_once.one_shot_ipc_test(SETTINGS)
        adapter.poll_once.assert_awaited_once_with()
        server.start.assert_called_once_with()
        server.stop.assert_called_once_with()
        self.assertEqual(server.call_args if hasattr(server, "call_args") else None, None)

    async def test_failed_rpc45_never_starts_http_listener(self):
        from sdk_snapshot_adapter import SDKSnapshotError
        adapter = Mock(poll_once=AsyncMock(
            side_effect=SDKSnapshotError("SDK_SESSION_FAILED")
        ))
        with patch.object(ipc_once, "SDKSnapshotAdapter", return_value=adapter), \
             patch.object(ipc_once, "SnapshotHTTPServer") as server:
            with self.assertRaises(SDKSnapshotError):
                await ipc_once.one_shot_ipc_test(SETTINGS)
        adapter.poll_once.assert_awaited_once_with()
        server.assert_not_called()

    async def test_http_failure_stops_server_and_clears_snapshot(self):
        adapter = Mock(poll_once=AsyncMock(return_value=fresh_snapshot()))
        server = Mock()
        server._server.server_address = ("127.0.0.1", 27800)
        snapshot_state = []
        async def fail_to_thread(func, port, token, state):
            snapshot_state.append(state)
            raise ValueError("test HTTP failure")
        with patch.object(ipc_once, "SDKSnapshotAdapter", return_value=adapter), \
             patch.object(ipc_once, "SnapshotHTTPServer", return_value=server), \
             patch.object(ipc_once.asyncio, "to_thread", side_effect=fail_to_thread):
            with self.assertRaises(ValueError):
                await ipc_once.one_shot_ipc_test(SETTINGS)
        self.assertEqual(snapshot_state[0], {})
        server.stop.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
