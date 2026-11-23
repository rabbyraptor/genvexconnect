"""Synthetic subprocess checks for SDK probe output bounds and cleanup.

No Nabto client, network, private keys, or Home Assistant dependencies.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from sdk_snapshot_adapter import SDKSnapshotAdapter, SDKSnapshotError


class ProbeOutputTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.profile = self.root / "private"
        self.profile.mkdir()
        self.probe = self.root / "candidate.py"
        self.probe.write_text("# fake probe file only\n")

    def adapter(self, code: str, timeout: float = 5.0) -> SDKSnapshotAdapter:
        return SDKSnapshotAdapter(
            device_id="123456789012",
            identity="test@example.invalid",
            unlock_secret="FAKE-UNLOCK-ONLY",
            profile_dir=str(self.profile),
            probe_file=str(self.probe),
            command=(sys.executable, "-u", "-c", code),
            timeout_seconds=timeout,
        )

    async def test_accepts_one_bounded_valid_snapshot(self):
        code = """
import sys, json
from datetime import datetime, timezone
settings = sys.stdin.read()
assert "FAKE-UNLOCK-ONLY" in settings
doc = {
  "schema_version": 1, "device_id": "123456789012",
  "timestamp_utc": datetime.now(timezone.utc).isoformat(),
  "health": "ok",
  "values": {"supply_air": 20.0, "outdoor_air": 5.0,
             "exhaust_air": 24.0, "extract_air": 22.0, "humidity": 50.0}
}
sys.stdout.write("GENVEX_READONLY_SNAPSHOT=" + json.dumps(doc) + "\\n")
"""
        doc = await self.adapter(code).poll_once()
        self.assertEqual(doc["values"]["humidity"], 50.0)

    async def test_oversize_stdout_fails_closed_without_hanging(self):
        code = 'import sys; sys.stdin.read(); sys.stdout.write("X" * 50000); sys.stdout.flush()'
        with self.assertRaises(SDKSnapshotError) as caught:
            await asyncio.wait_for(self.adapter(code).poll_once(), timeout=4)
        self.assertNotIn("X", str(caught.exception))

    async def test_timeout_kills_process_and_does_not_reveal_secret(self):
        code = 'import sys,time; sys.stdin.read(); time.sleep(8)'
        with self.assertRaises(SDKSnapshotError) as caught:
            await asyncio.wait_for(self.adapter(code, timeout=1).poll_once(), timeout=4)
        self.assertNotIn("FAKE-UNLOCK-ONLY", str(caught.exception))

    async def test_nonzero_exit_never_returns_stdout_or_credentials(self):
        code = 'import sys; sys.stdin.read(); print("FAKE-UNLOCK-ONLY"); sys.exit(3)'
        with self.assertRaises(SDKSnapshotError) as caught:
            await self.adapter(code).poll_once()
        self.assertNotIn("FAKE-UNLOCK-ONLY", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
