"""Offline async lifecycle tests; no vendor SDK or network."""
import asyncio
import unittest

from polling_worker import ReadOnlyPoller
from polling_service import PollingService
from snapshot_state import SnapshotState


class PollingServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_poll_and_stop_invalidate(self):
        seen = asyncio.Event()
        async def reader(_host, _addresses):
            seen.set()
            return [367, 299, 315, 377, 65]
        state = SnapshotState(ReadOnlyPoller(device_id="123456789012", reader=reader))
        service = PollingService(state)
        await service.start()
        await asyncio.wait_for(seen.wait(), 2)
        for _ in range(20):
            if state.current() is not None:
                break
            await asyncio.sleep(0.01)
        self.assertEqual(state.current()["values"]["humidity"], 65)
        await service.stop()
        self.assertIsNone(state.current())
        self.assertFalse(service.running)

    async def test_double_start_disallowed(self):
        async def reader(_host, _addresses):
            return [367, 299, 315, 377, 65]
        service = PollingService(SnapshotState(ReadOnlyPoller(device_id="123456789012", reader=reader)))
        await service.start()
        try:
            with self.assertRaises(RuntimeError):
                await service.start()
        finally:
            await service.stop()

    async def test_repeated_failures_leave_no_data_and_service_running(self):
        happened = asyncio.Event()
        async def reader(_host, _addresses):
            happened.set()
            raise OSError("not online")
        state = SnapshotState(ReadOnlyPoller(device_id="123456789012", reader=reader))
        service = PollingService(state)
        await service.start()
        await asyncio.wait_for(happened.wait(), 2)
        self.assertIsNone(state.current())
        self.assertTrue(service.running)
        await service.stop()

    async def test_cancellation_during_rpc(self):
        started = asyncio.Event()
        cancelled = asyncio.Event()
        async def reader(_host, _addresses):
            started.set()
            try:
                await asyncio.sleep(600)
            finally:
                cancelled.set()
        state = SnapshotState(ReadOnlyPoller(device_id="123456789012", reader=reader))
        service = PollingService(state)
        await service.start()
        await asyncio.wait_for(started.wait(), 2)
        await asyncio.wait_for(service.stop(), 2)
        self.assertTrue(cancelled.is_set())
        self.assertIsNone(state.current())

    async def test_recovery_after_error(self):
        happened = asyncio.Event()
        calls = 0
        async def reader(_host, _addresses):
            nonlocal calls
            calls += 1
            happened.set()
            if calls == 1:
                raise TimeoutError()
            return [367, 299, 315, 377, 65]
        state = SnapshotState(ReadOnlyPoller(device_id="123456789012", reader=reader))
        service = PollingService(state, interval_seconds=1)
        await service.start()
        try:
            await asyncio.wait_for(happened.wait(), 2)
            self.assertIsNone(state.current())
            for _ in range(150):
                if state.current() is not None:
                    break
                await asyncio.sleep(0.01)
            self.assertIsNotNone(state.current())
            self.assertGreaterEqual(calls, 2)
        finally:
            await service.stop()

    async def test_invalid_interval(self):
        async def reader(_host, _addresses):
            return [367, 299, 315, 377, 65]
        state = SnapshotState(ReadOnlyPoller(device_id="123456789012", reader=reader))
        for interval in (0, -1, 3601, True):
            with self.assertRaises(ValueError):
                PollingService(state, interval_seconds=interval)


if __name__ == "__main__":
    unittest.main()
