"""Offline fault-injection checks for the SDK subprocess lifecycle.

Uses only local Python child processes, never Nabto, credentials or network.
The tests verify hard timeout, cancellation and stdout-size safety bounds.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from sdk_snapshot_adapter import SDKSnapshotAdapter, SDKSnapshotError

DEVICE = "123456789012"


class ChildProcessSafetyTests(unittest.IsolatedAsyncioTestCase):
    def new_adapter(self, directory, child, *, timeout=3):
        probe = Path(directory) / "stub.py"
        probe.write_text("# local fixture only\n")
        return SDKSnapshotAdapter(
            device_id=DEVICE,
            identity="nobody@example.invalid",
            unlock_secret="dummy-secret",
            profile_dir=directory,
            probe_file=str(probe),
            timeout_seconds=timeout,
            command=(sys.executable, "-c", child),
        )

    async def test_timeout_terminates_hung_child_without_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            child = (
                "import sys,time\n"
                "sys.stdin.buffer.read()\n"
                "print('STARTED', flush=True)\n"
                "time.sleep(30)\n"
            )
            adapter = self.new_adapter(tmp, child, timeout=1)
            with self.assertRaises(SDKSnapshotError) as caught:
                await asyncio.wait_for(adapter.poll_once(), 5)
            self.assertEqual(caught.exception.code, "SDK_TIMEOUT")

    async def test_stdout_overflow_terminates_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            child = (
                "import sys,time\n"
                "sys.stdin.buffer.read()\n"
                "sys.stdout.buffer.write(b'X' * 40000)\n"
                "sys.stdout.buffer.flush()\n"
                "time.sleep(30)\n"
            )
            adapter = self.new_adapter(tmp, child, timeout=3)
            with self.assertRaises(SDKSnapshotError) as caught:
                await asyncio.wait_for(adapter.poll_once(), 6)
            self.assertEqual(caught.exception.code, "SDK_PROCESS_FAILURE")

    async def test_cancellation_kills_child_and_releases_adapter_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            ready = Path(tmp) / "child-ready"
            child = (
                "import pathlib,sys,time\n"
                "sys.stdin.buffer.read()\n"
                f"pathlib.Path({str(ready)!r}).write_text('ready')\n"
                "time.sleep(30)\n"
            )
            adapter = self.new_adapter(tmp, child, timeout=10)
            task = asyncio.create_task(adapter.poll_once())
            try:
                for _ in range(200):
                    if ready.exists():
                        break
                    await asyncio.sleep(.01)
                self.assertTrue(ready.exists(), "Child never started")
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(task, 4)
                # A cancelled attempt must not hold the single-flight lock.
                async with asyncio.timeout(1):
                    async with adapter._lock:
                        pass
            finally:
                if not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)


if __name__ == "__main__":
    unittest.main()
