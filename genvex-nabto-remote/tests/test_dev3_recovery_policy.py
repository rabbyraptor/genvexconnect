"""Offline, SDK-free tests for explicit opt-in RPC recovery candidate."""
import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from recovery_policy import eligible_for_one_retry, read_with_one_recovery
from sdk_snapshot_adapter import SDKSnapshotError


def error(*, code="SDK_RPC45_FAILED", status=26, events=(1000015,)):
    return SDKSnapshotError(code, rpc_status=status, rpc_events=events)


class RecoveryPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_recovery_after_matching_event(self):
        calls = 0
        sleeps = []
        result = {"health": "ok"}
        async def read():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise error()
            return result
        async def delay(seconds):
            sleeps.append(seconds)
        self.assertIs(await read_with_one_recovery(read, sleep=delay), result)
        self.assertEqual((calls, sleeps), (2, [60.0]))

    async def test_fails_closed_on_unknown_or_other_errors(self):
        for exc in (
            error(events=()),
            error(events=(1000026,)),
            error(events=(1000015, 1000026)),
            error(status=5),
            error(code="SDK_SESSION_FAILED"),
            SDKSnapshotError("SDK_TIMEOUT"),
            RuntimeError("private-details"),
        ):
            with self.subTest(exc=str(type(exc))):
                calls = 0
                sleeps = []
                async def read():
                    nonlocal calls
                    calls += 1
                    raise exc
                async def delay(seconds):
                    sleeps.append(seconds)
                with self.assertRaises(type(exc)):
                    await read_with_one_recovery(read, sleep=delay)
                self.assertEqual(calls, 1)
                self.assertEqual(sleeps, [])

    async def test_second_failure_is_final_no_third_attempt(self):
        calls = 0
        sleeps = []
        async def read():
            nonlocal calls
            calls += 1
            raise error()
        async def delay(seconds):
            sleeps.append(seconds)
        with self.assertRaises(SDKSnapshotError):
            await read_with_one_recovery(read, sleep=delay)
        self.assertEqual(calls, 2)
        self.assertEqual(sleeps, [60.0])

    async def test_success_does_not_sleep(self):
        calls = 0
        async def read():
            nonlocal calls
            calls += 1
            return {"health": "ok"}
        async def unexpected_sleep(_):
            self.fail("Successful read must not sleep")
        self.assertEqual(await read_with_one_recovery(read, sleep=unexpected_sleep),
                         {"health": "ok"})
        self.assertEqual(calls, 1)

    async def test_cancellation_during_delay_aborts_recovery(self):
        calls = 0
        sleeping = asyncio.Event()
        async def read():
            nonlocal calls
            calls += 1
            raise error()
        async def delay(_):
            sleeping.set()
            await asyncio.Event().wait()
        task = asyncio.create_task(read_with_one_recovery(read, sleep=delay))
        await asyncio.wait_for(sleeping.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(calls, 1)

    async def test_cancellation_on_first_attempt_never_retries(self):
        calls = 0
        async def read():
            nonlocal calls
            calls += 1
            raise asyncio.CancelledError
        async def unexpected_sleep(_):
            self.fail("Cancellation must not sleep")
        with self.assertRaises(asyncio.CancelledError):
            await read_with_one_recovery(read, sleep=unexpected_sleep)
        self.assertEqual(calls, 1)


class EligibilityTests(unittest.TestCase):
    def test_exact_event_only(self):
        self.assertTrue(eligible_for_one_retry(error()))
        self.assertFalse(eligible_for_one_retry(error(events=())))
        self.assertFalse(eligible_for_one_retry(error(status=None)))
        self.assertFalse(eligible_for_one_retry(ValueError("no")))


if __name__ == "__main__":
    unittest.main()
