"""Offline DEV3 tests for atomic polling state and the HA snapshot contract.

No Nabto SDK, Docker, network access or HA Core required.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

RUNTIME = Path(__file__).resolve().parents[1] / "runtime"
sys.path.insert(0, str(RUNTIME))

from polling_service import PollingService
from snapshot_contract import parse_snapshot
from snapshot_state import SnapshotState

DEVICE = "123456789012"
VALUES = {
    "supply_air": 6.7, "outdoor_air": 0.2, "exhaust_air": 1.8,
    "extract_air": 7.8, "humidity": 66.0,
}


def fresh_snapshot():
    return {
        "schema_version": 1,
        "device_id": DEVICE,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "health": "ok",
        "values": dict(VALUES),
    }


class FakePoller:
    device_id = DEVICE

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    async def poll_once(self):
        self.calls += 1
        result = self.outcomes.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class SnapshotStateTests(unittest.IsolatedAsyncioTestCase):
    async def test_publishes_one_complete_snapshot(self):
        worker = FakePoller([fresh_snapshot()])
        state = SnapshotState(worker)
        self.assertIsNone(state.current())
        self.assertTrue(await state.refresh())
        self.assertEqual(state.current()["values"], VALUES)
        self.assertEqual(state.generation, 1)

    async def test_copies_input_and_output(self):
        source = fresh_snapshot()
        state = SnapshotState(FakePoller([source]))
        self.assertTrue(await state.refresh())
        source["values"]["supply_air"] = -999
        self.assertEqual(state.current()["values"]["supply_air"], 6.7)
        output = state.current()
        output["values"]["humidity"] = -999
        self.assertEqual(state.current()["values"]["humidity"], 66.0)

    async def test_failed_refresh_clears_previous_success(self):
        state = SnapshotState(FakePoller([fresh_snapshot(), OSError("offline")]))
        self.assertTrue(await state.refresh())
        self.assertFalse(await state.refresh())
        self.assertIsNone(state.current())
        self.assertEqual(state.generation, 2)

    async def test_recovers_after_failure_without_old_values(self):
        replacement = fresh_snapshot()
        replacement["values"]["humidity"] = 67
        state = SnapshotState(FakePoller([
            fresh_snapshot(), RuntimeError("offline"), replacement,
        ]))
        self.assertTrue(await state.refresh())
        self.assertFalse(await state.refresh())
        self.assertIsNone(state.current())
        self.assertTrue(await state.refresh())
        self.assertEqual(state.current()["values"]["humidity"], 67)

    async def test_invalid_batch_never_published(self):
        source = fresh_snapshot()
        source["values"].pop("humidity")
        state = SnapshotState(FakePoller([source]))
        self.assertFalse(await state.refresh())
        self.assertIsNone(state.current())

    async def test_stale_reading_cleared_from_current(self):
        state = SnapshotState(FakePoller([fresh_snapshot()]))
        self.assertTrue(await state.refresh())
        # Simulate elapsed time without contacting the remote device.
        state._snapshot["timestamp_utc"] = (
            datetime.now(timezone.utc) - timedelta(seconds=200)
        ).isoformat()
        self.assertIsNone(state.current())
        self.assertIsNone(state.current())

    async def test_refreshes_are_serial(self):
        class LockedPoller:
            device_id = DEVICE
            active = 0
            maximum = 0

            async def poll_once(self):
                self.active += 1
                self.maximum = max(self.maximum, self.active)
                await asyncio.sleep(0.001)
                self.active -= 1
                return fresh_snapshot()

        worker = LockedPoller()
        state = SnapshotState(worker)
        results = await asyncio.gather(state.refresh(), state.refresh())
        self.assertEqual(results, [True, True])
        self.assertEqual(worker.maximum, 1)
        self.assertEqual(state.generation, 2)

    async def test_retains_only_fresh_prior_result_during_slow_refresh(self):
        started = asyncio.Event()
        release = asyncio.Event()

        class SlowPoller:
            device_id = DEVICE
            calls = 0
            async def poll_once(self):
                self.calls += 1
                if self.calls == 1:
                    return fresh_snapshot()
                started.set()
                await release.wait()
                return fresh_snapshot()

        state = SnapshotState(SlowPoller())
        self.assertTrue(await state.refresh())
        task = asyncio.create_task(state.refresh())
        await asyncio.wait_for(started.wait(), 1)
        self.assertEqual(state.current()["values"], VALUES)
        release.set()
        self.assertTrue(await task)
        self.assertIsNotNone(state.current())

    async def test_stale_prior_result_unavailable_during_slow_refresh(self):
        started = asyncio.Event()
        release = asyncio.Event()

        class SlowPoller:
            device_id = DEVICE
            calls = 0
            async def poll_once(self):
                self.calls += 1
                if self.calls == 1:
                    return fresh_snapshot()
                started.set()
                await release.wait()
                return fresh_snapshot()

        state = SnapshotState(SlowPoller())
        self.assertTrue(await state.refresh())
        state._snapshot["timestamp_utc"] = (
            datetime.now(timezone.utc) - timedelta(seconds=200)
        ).isoformat()
        task = asyncio.create_task(state.refresh())
        await asyncio.wait_for(started.wait(), 1)
        self.assertIsNone(state.current())
        release.set()
        self.assertTrue(await task)
        self.assertIsNotNone(state.current())

    async def test_cancelled_refresh_leaves_no_data(self):
        started = asyncio.Event()
        class BlockingPoller:
            device_id = DEVICE
            calls = 0
            async def poll_once(self):
                self.calls += 1
                if self.calls == 1:
                    return fresh_snapshot()
                started.set()
                await asyncio.Event().wait()

        state = SnapshotState(BlockingPoller())
        self.assertTrue(await state.refresh())
        task = asyncio.create_task(state.refresh())
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertIsNone(state.current())


class PollingServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_service_stops_and_invalidates(self):
        signal = asyncio.Event()
        seen = []
        state = SnapshotState(FakePoller([fresh_snapshot()]))

        async def on_result(ok):
            seen.append(ok)
            signal.set()

        service = PollingService(state, interval_seconds=60, on_result=on_result)
        await service.start()
        try:
            await asyncio.wait_for(signal.wait(), 1)
            self.assertEqual(seen, [True])
            self.assertTrue(service.running)
            self.assertIsNotNone(state.current())
        finally:
            await service.stop()
        self.assertFalse(service.running)
        self.assertIsNone(state.current())

    async def test_reject_duplicate_start(self):
        state = SnapshotState(FakePoller([fresh_snapshot()]))
        service = PollingService(state, interval_seconds=60)
        await service.start()
        try:
            with self.assertRaises(RuntimeError):
                await service.start()
        finally:
            await service.stop()

    async def test_stop_invalidates_even_if_poll_task_crashed(self):
        state = SnapshotState(FakePoller([fresh_snapshot()]))
        self.assertTrue(await state.refresh())
        self.assertIsNotNone(state.current())
        service = PollingService(state, interval_seconds=60)

        async def crash():
            raise RuntimeError("synthetic internal task crash")

        service._task = asyncio.create_task(crash())
        await asyncio.sleep(0)
        with self.assertRaises(RuntimeError):
            await service.stop()
        self.assertIsNone(service._task)
        self.assertIsNone(state.current())

    async def test_reject_bool_interval(self):
        with self.assertRaises(ValueError):
            PollingService(SnapshotState(FakePoller([])), interval_seconds=True)


if __name__ == "__main__":
    unittest.main()
