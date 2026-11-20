"""No network: exercises serial polling contract and stale-data avoidance."""
import asyncio
import unittest

from polling_worker import PollFailed, ReadOnlyPoller
from snapshot_contract import parse_snapshot


class PollerTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_five_address_batch(self):
        calls = []
        async def reader(host, addresses):
            calls.append((host, addresses))
            return [365, 301, 315, 376, 66]
        worker = ReadOnlyPoller(device_id="123456789012", reader=reader)
        response = await worker.poll_once()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], (20, 21, 22, 23, 26))
        self.assertEqual(parse_snapshot(response, expected_device_id="123456789012")["humidity"], 66.0)

    async def test_no_overlapping_calls(self):
        active = 0
        max_active = 0
        async def reader(_host, _addresses):
            nonlocal active, max_active
            active += 1
            max_active = max(active, max_active)
            try:
                await asyncio.sleep(0.03)
                return [365, 301, 315, 376, 66]
            finally:
                active -= 1
        worker = ReadOnlyPoller(device_id="123456789012", reader=reader)
        results = await asyncio.gather(worker.poll_once(), worker.poll_once(), worker.poll_once())
        self.assertEqual(len(results), 3)
        self.assertEqual(max_active, 1)

    async def test_reject_incomplete_response(self):
        async def reader(_host, _addresses):
            return [365, 301]
        worker = ReadOnlyPoller(device_id="123456789012", reader=reader)
        with self.assertRaises(PollFailed):
            await worker.poll_once()

    async def test_timeout_and_recover(self):
        attempts = 0
        async def reader(_host, _addresses):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                await asyncio.sleep(2)
            return [365, 301, 315, 376, 66]
        worker = ReadOnlyPoller(device_id="123456789012", reader=reader, timeout_seconds=1)
        with self.assertRaises(PollFailed):
            await worker.poll_once()
        self.assertEqual((await worker.poll_once())["values"]["supply_air"], 6.5)

    async def test_never_leaks_sdk_errors(self):
        async def reader(_host, _addresses):
            raise RuntimeError("SENSITIVE_ACCOUNT_SECRET")
        worker = ReadOnlyPoller(device_id="123456789012", reader=reader)
        with self.assertRaises(PollFailed) as ctx:
            await worker.poll_once()
        self.assertNotIn("SENSITIVE", str(ctx.exception))

    async def test_input_validation(self):
        async def reader(_host, _addresses):
            return [365, 301, 315, 376, 66]
        with self.assertRaises(ValueError):
            ReadOnlyPoller(device_id="123", reader=reader)
        with self.assertRaises(ValueError):
            ReadOnlyPoller(device_id="123456789012", reader=reader, timeout_seconds=0)


if __name__ == "__main__":
    unittest.main()
