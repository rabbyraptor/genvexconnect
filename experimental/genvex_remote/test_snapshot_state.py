"""Tests deliberately use fake values and no Nabto/HTTP access."""
import asyncio
from datetime import datetime, timedelta, timezone
import unittest

from polling_worker import ReadOnlyPoller
from snapshot_state import SnapshotState


class SnapshotStateTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_then_failure_clears_last_good(self):
        calls = 0
        async def rpc(_host, _addresses):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("private upstream error")
            return [367, 299, 315, 377, 65]
        state = SnapshotState(ReadOnlyPoller(device_id="123456789012", reader=rpc))
        self.assertIsNone(state.current())
        self.assertTrue(await state.refresh())
        self.assertEqual(state.current()["values"]["supply_air"], 6.7)
        self.assertFalse(await state.refresh())
        self.assertIsNone(state.current())
        self.assertTrue(await state.refresh())
        self.assertEqual(state.current()["values"]["humidity"], 65.0)

    async def test_detached_values_prevent_mutation(self):
        async def rpc(_host, _addresses):
            return [367, 299, 315, 377, 65]
        state = SnapshotState(ReadOnlyPoller(device_id="123456789012", reader=rpc))
        await state.refresh()
        one = state.current()
        one["values"]["humidity"] = 1234
        self.assertEqual(state.current()["values"]["humidity"], 65.0)

    async def test_no_old_data_visible_during_refresh(self):
        start = asyncio.Event()
        finish = asyncio.Event()
        calls = 0
        async def rpc(_host, _addresses):
            nonlocal calls
            calls += 1
            if calls == 2:
                start.set()
                await finish.wait()
            return [367, 299, 315, 377, 65]
        state = SnapshotState(ReadOnlyPoller(device_id="123456789012", reader=rpc))
        self.assertTrue(await state.refresh())
        task = asyncio.create_task(state.refresh())
        await start.wait()
        self.assertIsNone(state.current())
        finish.set()
        self.assertTrue(await task)
        self.assertIsNotNone(state.current())

    async def test_serial_state_refresh(self):
        active = 0
        maximum = 0
        async def rpc(_host, _addresses):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            try:
                await asyncio.sleep(0.01)
                return [367, 299, 315, 377, 65]
            finally:
                active -= 1
        state = SnapshotState(ReadOnlyPoller(device_id="123456789012", reader=rpc))
        self.assertEqual(await asyncio.gather(*[state.refresh() for _ in range(3)]), [True]*3)
        self.assertEqual(maximum, 1)
        self.assertEqual(state.generation, 3)


if __name__ == "__main__":
    unittest.main()
