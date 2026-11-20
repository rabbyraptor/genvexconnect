"""Offline regression tests for the opt-in, single-shot RPC45 entrypoint."""
import asyncio
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

RUNTIME = Path(__file__).resolve().parents[1] / "runtime"
sys.path.insert(0, str(RUNTIME))

import live_once


class FakeStdin:
    def __init__(self, data):
        self.buffer = io.BytesIO(data)


class SettingsTests(unittest.TestCase):
    def test_valid_input(self):
        payload = {"device_id": "abc123", "identity": "test@example.com",
                   "unlock_secret": "not-a-real-secret"}
        with patch.object(sys, "stdin", FakeStdin((json.dumps(payload) + "\n").encode())):
            with patch.object(live_once, "remote_hostname", return_value="device.invalid"):
                self.assertEqual(live_once.read_settings(), payload)

    def test_reject_extra_line(self):
        payload = b'{"device_id":"abc","identity":"a","unlock_secret":"b"}\nextra\n'
        with patch.object(sys, "stdin", FakeStdin(payload)):
            with patch.object(live_once, "remote_hostname", return_value="device.invalid"):
                with self.assertRaises(ValueError):
                    live_once.read_settings()

    def test_reject_oversize(self):
        with patch.object(sys, "stdin", FakeStdin(b"x" * 4097 + b"\n")):
            with self.assertRaises(ValueError):
                live_once.read_settings()

    def test_reject_unknown_field(self):
        payload = b'{"device_id":"abc","identity":"a","unlock_secret":"b","extra":1}\n'
        with patch.object(sys, "stdin", FakeStdin(payload)):
            with self.assertRaises(ValueError):
                live_once.read_settings()

    def test_reject_newline_in_secret(self):
        payload = b'{"device_id":"abc","identity":"a","unlock_secret":"b\\nc"}\n'
        with patch.object(sys, "stdin", FakeStdin(payload)):
            with patch.object(live_once, "remote_hostname", return_value="device.invalid"):
                with self.assertRaises(ValueError):
                    live_once.read_settings()

    def test_no_credentials_in_failure_output(self):
        payload = {"device_id": "abc", "identity": "private@example.com",
                   "unlock_secret": "sensitive"}
        with patch.object(live_once, "read_settings", return_value=payload), \
             patch.object(live_once, "validate_private_profile", side_effect=ValueError("sensitive")), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(live_once.main(), 1)
            self.assertNotIn("sensitive", output.getvalue())
            self.assertNotIn("private@example.com", output.getvalue())


class SingleReadTests(unittest.IsolatedAsyncioTestCase):
    async def test_exactly_one_adapter_poll(self):
        settings = {"device_id": "abc", "identity": "a", "unlock_secret": "b"}
        fake = AsyncMock()
        fake.poll_once.return_value = {"example": 1}
        with patch.object(live_once, "SDKSnapshotAdapter", return_value=fake) as adapter, \
             patch.object(live_once, "parse_snapshot") as validate, \
             patch("sys.stdout", new_callable=io.StringIO):
            await live_once.read_once(settings)
        adapter.assert_called_once()
        fake.poll_once.assert_awaited_once()
        validate.assert_called_once_with({"example": 1}, expected_device_id="abc")


if __name__ == "__main__":
    unittest.main()
