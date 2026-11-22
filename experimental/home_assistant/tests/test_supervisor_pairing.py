"""Offline fake-Supervisor Core pairing tests; no live API credentials."""
from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/genvex_remote"
spec = importlib.util.spec_from_file_location("genvex_supervisor_pairing", ROOT / "supervisor_pairing.py")
pairing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pairing)


def fake_info():
    return {
        "result": "ok",
        "data": {
            "slug": "local_genvex_nabto_remote",
            "state": "started",
            "options": {
                "device_id": "123456789012",
                "ipc_token": "Z" * 43,
                "identity": "NOT_TO_BE_LOGGED@example.invalid",
                "unlock_secret": "NOT_TO_BE_LOGGED",
            },
        },
    }


class SupervisorPairingTests(unittest.TestCase):
    def test_core_only_record_yields_token(self):
        record = fake_info()
        self.assertEqual(
            pairing.extract_app_ipc_token(record, expected_device_id="123456789012"),
            "Z" * 43,
        )

    def test_wrong_device_and_app_fail_closed(self):
        record = fake_info()
        with self.assertRaises(pairing.SupervisorPairingUnavailable):
            pairing.extract_app_ipc_token(record, expected_device_id="999999999999")
        record["data"]["slug"] = "other_app"
        with self.assertRaises(pairing.SupervisorPairingUnavailable):
            pairing.extract_app_ipc_token(record, expected_device_id="123456789012")

    def test_rejects_stopped_or_redacted(self):
        record = fake_info()
        record["data"]["state"] = "stopped"
        with self.assertRaises(pairing.SupervisorPairingUnavailable):
            pairing.extract_app_ipc_token(record, expected_device_id="123456789012")
        record["data"]["state"] = "started"
        record["data"]["options"] = {}
        with self.assertRaises(pairing.SupervisorPairingUnavailable):
            pairing.extract_app_ipc_token(record, expected_device_id="123456789012")

    def test_invalid_tokens_and_responses_never_leak(self):
        for token in ("short", "A" * 39, "B" * 129, "A" * 42 + "\n", None):
            with self.subTest(token=type(token).__name__):
                record = fake_info()
                record["data"]["options"]["ipc_token"] = token
                try:
                    pairing.extract_app_ipc_token(record, expected_device_id="123456789012")
                except pairing.SupervisorPairingUnavailable as error:
                    self.assertEqual(str(error), "Trusted App pairing unavailable")
                    self.assertNotIn("NOT_TO_BE_LOGGED", str(error))
                else:
                    self.fail("Invalid token accepted")
        for invalid in ({}, {"result": "error"}, None, [], {"result": "ok", "data": None}):
            with self.assertRaises(pairing.SupervisorPairingUnavailable):
                pairing.extract_app_ipc_token(invalid, expected_device_id="123456789012")



class CorePairingAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_uses_fixed_app_id_and_returns_only_token(self):
        called = []

        async def load(app_id):
            called.append(app_id)
            return fake_info()

        token = await pairing.async_load_app_ipc_token(
            load, expected_device_id="123456789012"
        )
        self.assertEqual(token, "Z" * 43)
        self.assertEqual(called, [pairing.APP_ID])

    async def test_bad_device_fails_before_loader_invocation(self):
        called = []

        async def load(app_id):
            called.append(app_id)
            return fake_info()

        with self.assertRaises(pairing.SupervisorPairingUnavailable):
            await pairing.async_load_app_ipc_token(
                load, expected_device_id="12345678901x"
            )
        self.assertEqual(called, [])

    async def test_transport_errors_are_sanitized(self):
        async def load(_app_id):
            raise RuntimeError("FAKE-SUPERVISOR-SECRET")

        with self.assertRaises(pairing.SupervisorPairingUnavailable) as caught:
            await pairing.async_load_app_ipc_token(
                load, expected_device_id="123456789012"
            )
        self.assertNotIn("FAKE-SUPERVISOR-SECRET", str(caught.exception))

    async def test_mismatched_device_fails_closed(self):
        async def load(_app_id):
            info = fake_info()
            info["data"]["options"]["device_id"] = "999999999999"
            return info

        with self.assertRaises(pairing.SupervisorPairingUnavailable):
            await pairing.async_load_app_ipc_token(
                load, expected_device_id="123456789012"
            )

    async def test_timeout_is_bounded_and_sanitized(self):
        async def load(_app_id):
            await asyncio.sleep(5)
            return fake_info()

        with self.assertRaises(pairing.SupervisorPairingUnavailable) as caught:
            await pairing.async_load_app_ipc_token(
                load, expected_device_id="123456789012",
                timeout_seconds=0.01,
            )
        self.assertEqual(str(caught.exception), "Trusted App pairing unavailable")

    async def test_cancellation_propagates(self):
        entered = asyncio.Event()

        async def load(_app_id):
            entered.set()
            await asyncio.sleep(60)

        task = asyncio.create_task(pairing.async_load_app_ipc_token(
            load, expected_device_id="123456789012"
        ))
        await asyncio.wait_for(entered.wait(), timeout=1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task


if __name__ == "__main__":
    unittest.main()
