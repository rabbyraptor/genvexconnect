"""Offline fake-Supervisor Core pairing tests; no live API credentials."""
from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
