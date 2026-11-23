"""Offline-only tests: no SDK, credentials, network or Home Assistant."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import unittest

from v2_polling_state import ReadOnlyV2Poller, V2PollFailed, V2SnapshotState

DEVICE = "123456789012"
RAW = (368, 308, 322, 378, 67, 6000, 5800)
ADDRESSES = (20, 21, 22, 23, 26, 18, 19)


class V2PollingTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_atomic_rpc_with_seven_fixed_addresses(self):
        calls = []

        async def reader(host, addresses):
            calls.append((host, addresses))
            return RAW

        state = V2SnapshotState(ReadOnlyV2Poller(device_id=DEVICE, reader=reader))
        self.assertIsNone(state.current())
        self.assertTrue(await state.refresh())
        self.assertEqual(calls, [(DEVICE + ".remote.lscontrol.dk", ADDRESSES)])
        payload = state.current()
        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["values"]["supply_air"], 6.8)
        self.assertEqual(payload["values"]["humidity"], 67.0)
        self.assertEqual(payload["optional"]["fan_duty"], {
            "fan_duty_supply": 60.0, "fan_duty_extract": 58.0
        })
        self.assertEqual(state.generation, 1)

    async def test_invalid_optional_pair_never_fabricates_zero(self):
        async def reader(_host, _addresses):
            return RAW[:5] + (10001, 5800)

        state = V2SnapshotState(ReadOnlyV2Poller(device_id=DEVICE, reader=reader))
        self.assertTrue(await state.refresh())
        result = state.current()
        self.assertEqual(result["values"]["humidity"], 67.0)
        self.assertEqual(result["optional"]["fan_duty"], {})

    async def test_incomplete_baseline_and_failed_followup_invalidate(self):
        readings = iter((RAW, RAW[:4], RAW))

        async def reader(_host, _addresses):
            return next(readings)

        state = V2SnapshotState(ReadOnlyV2Poller(device_id=DEVICE, reader=reader))
        self.assertTrue(await state.refresh())
        self.assertIsNotNone(state.current())
        self.assertFalse(await state.refresh())
        self.assertIsNone(state.current())
        self.assertTrue(await state.refresh())
        self.assertIsNotNone(state.current())
        self.assertEqual(state.generation, 3)
        state.invalidate()
        self.assertIsNone(state.current())

    async def test_exception_redacted_and_previous_snapshot_cleared(self):
        count = 0

        async def reader(_host, _addresses):
            nonlocal count
            count += 1
            if count == 1:
                return RAW
            raise RuntimeError("private credentials should never leak")

        poller = ReadOnlyV2Poller(device_id=DEVICE, reader=reader)
        state = V2SnapshotState(poller)
        self.assertTrue(await state.refresh())
        with self.assertRaises(V2PollFailed) as ctx:
            await poller.poll_once()
        self.assertNotIn("private credentials", str(ctx.exception))
        self.assertFalse(await state.refresh())
        self.assertIsNone(state.current())

    async def test_serial_rpc_even_with_concurrent_calls(self):
        active = 0
        max_active = 0

        async def reader(_host, _addresses):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.005)
            active -= 1
            return RAW

        poller = ReadOnlyV2Poller(device_id=DEVICE, reader=reader)
        results = await asyncio.gather(poller.poll_once(), poller.poll_once())
        self.assertEqual(len(results), 2)
        self.assertEqual(max_active, 1)

    async def test_stale_and_tampered_snapshot_unavailable(self):
        async def reader(_host, _addresses):
            return RAW

        state = V2SnapshotState(ReadOnlyV2Poller(device_id=DEVICE, reader=reader))
        self.assertTrue(await state.refresh())
        state._snapshot["timestamp_utc"] = (
            datetime.now(timezone.utc) - timedelta(minutes=5)
        ).isoformat()
        self.assertIsNone(state.current())
        self.assertTrue(await state.refresh())
        state._snapshot["optional"]["fan_duty"]["fan_duty_extract"] = 101
        self.assertIsNone(state.current())

    async def test_cancel_is_not_converted_to_failure(self):
        started = asyncio.Event()

        async def reader(_host, _addresses):
            started.set()
            await asyncio.Event().wait()

        poller = ReadOnlyV2Poller(device_id=DEVICE, reader=reader)
        task = asyncio.create_task(poller.poll_once())
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

    def test_invalid_config_fails_closed(self):
        async def reader(_host, _addresses):
            return RAW

        for timeout in (True, 0, 76, "30"):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                ReadOnlyV2Poller(
                    device_id=DEVICE, reader=reader, timeout_seconds=timeout
                )
        with self.assertRaises(ValueError):
            ReadOnlyV2Poller(device_id="wrong", reader=reader)


if __name__ == "__main__":
    unittest.main()
