"""Offline tests for metadata-only RPC45 diagnostics; fake SDK, no credentials."""
from __future__ import annotations

import asyncio
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from polling_service import PollingService
from snapshot_state import SnapshotState


class _FakeAdapter:
    device_id = "123456789012"

    def __init__(self, *, error=None):
        self._proc = type("Process", (), {"pid": 99})()
        self.error = error

    async def poll_once(self):
        if self.error is not None:
            raise self.error
        return {
            "schema_version": 1,
            "device_id": self.device_id,
            "timestamp_utc": "2099-01-01T00:00:00+00:00",
            "health": "ok",
            "values": {
                "supply_air": 5.0, "outdoor_air": 2.0,
                "exhaust_air": 8.0, "extract_air": 6.0, "humidity": 55.0,
            },
        }


class _SDKFailure(Exception):
    rpc_status = 26
    elapsed_ms = 5050


class DiagnosticTests(unittest.IsolatedAsyncioTestCase):
    async def test_service_logs_sanitized_success_and_pid(self):
        class FakeState:
            _poller = _FakeAdapter()

            async def refresh(self):
                return True

            def invalidate(self):
                pass

        arrived = asyncio.Event()

        async def on_result(ok):
            self.assertTrue(ok)
            arrived.set()

        output = StringIO()
        with redirect_stdout(output):
            service = PollingService(FakeState(), interval_seconds=60, on_result=on_result)
            await service.start()
            try:
                await asyncio.wait_for(arrived.wait(), timeout=2)
            finally:
                await service.stop()

        line = output.getvalue()
        self.assertIn("RPC45 ", line)
        self.assertIn(" OK ", line)
        self.assertIn("PID_BEFORE=99 PID_AFTER=99", line)

    async def test_sdk_failure_logs_only_numeric_metadata(self):
        secret = "SHOULD_NOT_APPEAR_IN_LOG"
        adapter = _FakeAdapter(error=_SDKFailure(secret))
        state = SnapshotState(adapter)
        output = StringIO()

        with redirect_stdout(output):
            ok = await state.refresh()

        self.assertFalse(ok)
        self.assertIsNone(state.current())
        self.assertIn("rpc_status=26", output.getvalue())
        self.assertIn("elapsed_ms=5050", output.getvalue())
        self.assertNotIn(secret, output.getvalue())

    async def test_unknown_failure_does_not_print_exception(self):
        secret = "SHOULD_NOT_APPEAR_IN_LOG"
        state = SnapshotState(_FakeAdapter(error=RuntimeError(secret)))
        output = StringIO()

        with redirect_stdout(output):
            self.assertFalse(await state.refresh())

        self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
