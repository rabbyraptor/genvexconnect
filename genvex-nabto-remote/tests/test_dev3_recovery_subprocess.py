"""SDK-free subprocess contract: recovery uses two independently spawned readers.

This executes only a tiny local Python fixture, never the Nabto SDK, network,
Docker, Home Assistant, account or profile key. The fake child's output has the
same allowlisted format as the isolated QEMU diagnostic probe.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))

from recovery_policy import read_with_one_recovery
from sdk_snapshot_adapter import SDKSnapshotAdapter, SDKSnapshotError


DEVICE = "123456789012"

# Each invocation runs a new interpreter and observes a shared counter. The
# child's first request returns the real field-test's sanitized error markers.
# The next request emits one complete, ordinary five-sensor snapshot.
CHILD = r"""
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

data = sys.stdin.buffer.read()
assert data and b"example.invalid" in data
counter = Path(sys.argv[1])
attempt = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(attempt))
with open(str(counter) + ".pids", "a", encoding="ascii") as pids:
    pids.write(str(os.getpid()) + "\n")
if attempt == 1:
    print("SDK startup: 0")
    print("Resources: 0")
    print("Profile session: 0")
    print("Candidate XML registered: 0")
    print("Batch RPC status: 26")
    print("RPC elapsed_ms: 13772")
    print("Diagnostic: ('ERROR_JSON', [1000015])")
    raise SystemExit(6)
if attempt == 2:
    snapshot = {
        "schema_version": 1,
        "device_id": "123456789012",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "health": "ok",
        "values": {
            "supply_air": 6.7, "outdoor_air": 0.2, "exhaust_air": 1.8,
            "extract_air": 7.8, "humidity": 66.0,
        },
    }
    print("GENVEX_READONLY_SNAPSHOT=" + json.dumps(snapshot))
    raise SystemExit(0)
raise SystemExit(7)
"""


class ProcessRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_fresh_subprocesses_and_one_complete_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dummy_probe = root / "empty_probe.py"
            dummy_probe.write_text("# Not used by local fake child\n")
            counter = root / "attempts"
            adapter = SDKSnapshotAdapter(
                device_id=DEVICE,
                identity="test@example.invalid",
                unlock_secret="not-real",
                profile_dir=tmp,
                probe_file=str(dummy_probe),
                timeout_seconds=10,
                command=(sys.executable, "-c", CHILD, str(counter)),
            )
            sleeps = []
            async def delay(seconds):
                sleeps.append(seconds)
            snapshot = await read_with_one_recovery(adapter.poll_once, sleep=delay)
            self.assertEqual(snapshot["values"]["humidity"], 66.0)
            self.assertEqual(snapshot["device_id"], DEVICE)
            self.assertEqual(counter.read_text(), "2")
            pids = (root / "attempts.pids").read_text().splitlines()
            self.assertEqual(len(pids), 2)
            self.assertNotEqual(pids[0], pids[1])
            self.assertEqual(sleeps, [60.0])

    async def test_nonmatching_event_never_spawns_second_child(self):
        other = CHILD.replace("[1000015]", "[1000026]")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dummy_probe = root / "empty_probe.py"
            dummy_probe.write_text("# fake only\n")
            counter = root / "attempts"
            adapter = SDKSnapshotAdapter(
                device_id=DEVICE,
                identity="test@example.invalid",
                unlock_secret="not-real",
                profile_dir=tmp,
                probe_file=str(dummy_probe),
                timeout_seconds=10,
                command=(sys.executable, "-c", other, str(counter)),
            )
            async def no_delay(_):
                self.fail("Nonmatching event should not delay/retry")
            with self.assertRaises(SDKSnapshotError) as caught:
                await read_with_one_recovery(adapter.poll_once, sleep=no_delay)
            self.assertEqual(caught.exception.code, "SDK_RPC45_FAILED")
            self.assertEqual(caught.exception.rpc_events, (1000026,))
            self.assertEqual(counter.read_text(), "1")


if __name__ == "__main__":
    unittest.main()
