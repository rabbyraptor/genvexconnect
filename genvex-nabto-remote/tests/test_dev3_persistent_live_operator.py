"""Offline contract for the bounded live persistent adapter operator.

Uses a fake adapter, no HAOS, QEMU, vendor SDK, account or remote connection.
"""
from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import io

ROOT = Path(__file__).resolve().parents[1] / "runtime"
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("persistent_live_gate", ROOT / "persistent_live_gate.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

from sdk_snapshot_adapter import SDKSnapshotError


class FakeProcess:
    def __init__(self, pid):
        self.pid = pid


class FakeAdapter:
    device_id = "123456789012"

    def __init__(self, statuses):
        self.statuses = iter(statuses)
        self._proc = None
        self.closed = False

    async def poll_once(self):
        if self._proc is None:
            self._proc = FakeProcess(123)
        status = next(self.statuses)
        if status == 26:
            raise SDKSnapshotError("SDK_RPC45_FAILED", rpc_status=26)
        return {
            "schema_version": 1,
            "device_id": self.device_id,
            "timestamp_utc": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc).isoformat(),
            "health": "ok",
            "values": {
                "supply_air": 7.1, "outdoor_air": 3.5,
                "exhaust_air": 4.4, "extract_air": 7.9, "humidity": 66.0,
            },
        }

    async def aclose(self):
        self._proc = None
        self.closed = True


class OperatorOfflineTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_status26_recovery_with_same_worker(self):
        fake = FakeAdapter([0, 26, 0, 0, 0, 0])
        sleeps = []
        async def delay(seconds):
            sleeps.append(seconds)
        output = io.StringIO()
        with patch("sys.stdout", output):
            result = await module.run_trial(fake, sleep=delay)
        self.assertEqual(result["success"], 5)
        self.assertTrue(result["recovered"])
        self.assertEqual(result["workers"], 1)
        self.assertEqual(sleeps, [60] * 5)
        self.assertTrue(fake.closed)
        self.assertIn("WORKER_CLOSED: True", output.getvalue())

    async def test_all_successes_is_not_falsely_reported_recovery(self):
        fake = FakeAdapter([0] * 6)
        async def delay(_): pass
        with patch("sys.stdout", io.StringIO()):
            result = await module.run_trial(fake, sleep=delay)
        self.assertEqual(result["success"], 6)
        self.assertFalse(result["recovered"])
        self.assertTrue(fake.closed)

    async def test_source_is_inert_on_import(self):
        self.assertEqual(module.ATTEMPTS, 6)
        self.assertEqual(module.INTERVAL, 60)

if __name__ == "__main__":
    unittest.main()
