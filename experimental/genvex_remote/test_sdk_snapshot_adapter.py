"""Offline subprocess tests; no Nabto SDK, credentials, internet or HA."""
import asyncio
import json
import sys
import tempfile
from pathlib import Path
import unittest

from sdk_snapshot_adapter import SDKSnapshotAdapter, SDKSnapshotError, parse_probe_output
from snapshot_state import SnapshotState
from polling_service import PollingService


_FAKE = r"""
import datetime, json, sys
lines = [sys.stdin.readline().strip() for _ in range(3)]
if lines != ["mock_user", "123456789012.remote.lscontrol.dk", "mock_secret"]:
    raise SystemExit(1)
snapshot = {
 "schema_version": 1, "device_id": "123456789012",
 "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "health": "ok",
 "values": {
  "supply_air": 6.7, "outdoor_air": -0.1, "exhaust_air": 1.5,
  "extract_air": 7.7, "humidity": 65.0,
 }
}
print("GENVEX_READONLY_SNAPSHOT=" + json.dumps(snapshot))
"""


class SDKAdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / "probe.py").write_text("# fake test only\n")
        self.profile = str(root)
        self.probe = str(root / "probe.py")

    def adapter(self, snippet=_FAKE, timeout=2):
        return SDKSnapshotAdapter(
            device_id="123456789012", identity="mock_user",
            unlock_secret="mock_secret", profile_dir=self.profile,
            probe_file=self.probe, timeout_seconds=timeout,
            command=(sys.executable, "-c", snippet),
        )

    async def test_real_subprocess_mock_success(self):
        response = await self.adapter().poll_once()
        self.assertEqual(response["values"]["humidity"], 65)

    async def test_json_marker_parser_regression(self):
        from datetime import datetime, timezone
        payload = {
            "schema_version": 1,
            "device_id": "123456789012",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "health": "ok",
            "values": {
                "supply_air": 6.7, "outdoor_air": -0.1,
                "exhaust_air": 1.5, "extract_air": 7.7, "humidity": 65.0,
            },
        }
        output = ("diagnostic message\nGENVEX_READONLY_SNAPSHOT="
                  + json.dumps(payload) + "\n").encode()
        self.assertEqual(
            parse_probe_output(output, device_id="123456789012")["values"]["humidity"],
            65.0,
        )

    async def test_adapter_is_compatible_with_snapshot_state_and_poller(self):
        state = SnapshotState(self.adapter())
        service = PollingService(state)
        await service.start()
        try:
            for _ in range(100):
                if state.current():
                    break
                await asyncio.sleep(0.02)
            self.assertEqual(state.current()["values"]["supply_air"], 6.7)
        finally:
            await service.stop()
        self.assertIsNone(state.current())

    async def test_exit_nonzero_not_exposing_output(self):
        adapter = self.adapter('import sys; print("PRIVATE-SECRET"); sys.exit(2)')
        with self.assertRaises(SDKSnapshotError) as result:
            await adapter.poll_once()
        self.assertNotIn("PRIVATE-SECRET", str(result.exception))

    async def test_timeout_kills_process(self):
        adapter = self.adapter("import time; time.sleep(30)", timeout=1)
        with self.assertRaises(SDKSnapshotError):
            await adapter.poll_once()

    async def test_cancel_ongoing_process(self):
        adapter = self.adapter("import time; time.sleep(30)", timeout=60)
        task = asyncio.create_task(adapter.poll_once())
        await asyncio.sleep(0.1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)

    async def test_invalid_marker(self):
        adapter = self.adapter('print("SDK hello, no snapshot")')
        with self.assertRaises(SDKSnapshotError):
            await adapter.poll_once()

    async def test_duplicate_or_fake_marker(self):
        with self.assertRaises(SDKSnapshotError):
            parse_probe_output(
                b"GENVEX_READONLY_SNAPSHOT={}\nGENVEX_READONLY_SNAPSHOT={}\n",
                device_id="123456789012",
            )

    async def test_reject_identity_newline(self):
        with self.assertRaises(ValueError):
            SDKSnapshotAdapter(
                device_id="123456789012", identity="fake\nuser",
                unlock_secret="mock_secret", profile_dir=self.profile,
                probe_file=self.probe,
            )


if __name__ == "__main__":
    unittest.main()
