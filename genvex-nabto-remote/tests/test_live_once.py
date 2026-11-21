"""Offline regression tests for the opt-in, single-shot RPC45 entrypoint."""
import asyncio
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch, Mock

RUNTIME = Path(__file__).resolve().parents[1] / "runtime"
sys.path.insert(0, str(RUNTIME))

import live_once
from sdk_snapshot_adapter import classify_probe_failure, SDKSnapshotError


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
        with patch.object(sys, "argv", ["live_once.py"]), \
             patch.object(live_once, "read_settings", return_value=payload), \
             patch.object(live_once, "validate_private_profile", side_effect=ValueError("sensitive")), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(live_once.main(), 1)
            self.assertNotIn("sensitive", output.getvalue())
            self.assertNotIn("private@example.com", output.getvalue())

    def test_safe_sdk_failure_code(self):
        payload = {"device_id": "123456789012", "identity": "private@example.com",
                   "unlock_secret": "sensitive"}
        with patch.object(live_once, "read_settings", return_value=payload), \
             patch.object(live_once, "validate_private_profile"), \
             patch.object(live_once, "PROBE", Mock(is_file=lambda: True)), \
             patch.object(live_once, "read_once", new_callable=AsyncMock,
                          side_effect=SDKSnapshotError("SDK_SESSION_FAILED")), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(live_once.main(), 1)
            self.assertIn("BLOCKED: SDK_SESSION_FAILED", output.getvalue())
            self.assertNotIn("sensitive", output.getvalue())
            self.assertNotIn("private@example.com", output.getvalue())

    def test_reject_extra_cli_flags_without_reading_secrets(self):
        with patch.object(sys, "argv", ["live_once.py", "--show-values", "--debug"]), \
             patch.object(live_once, "read_settings") as read_settings, \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(live_once.main(), 1)
            read_settings.assert_not_called()
            self.assertEqual(output.getvalue(), "BLOCKED: INPUT_INVALID\\n")


class FailureClassificationTests(unittest.TestCase):
    def test_sdk_session_error(self):
        self.assertEqual(classify_probe_failure(
            b"SDK startup: 0\nResources: 0\nProfile session: 3\n"),
            "SDK_SESSION_FAILED")

    def test_rpc_error(self):
        self.assertEqual(classify_probe_failure(
            b"SDK startup: 0\nProfile session: 0\n"
            b"Candidate XML registered: 0\nBatch RPC status: 5\n"),
            "SDK_RPC45_FAILED")

    def test_successful_rpc_but_no_snapshot(self):
        self.assertEqual(classify_probe_failure(
            b"Batch RPC status: 0\n"),
            "SDK_RESPONSE_INVALID")

    def test_never_reflects_untrusted_diagnostics(self):
        self.assertEqual(
            classify_probe_failure(b"secret@example.com\nsecret=abc\n"),
            "SDK_EARLY_EXIT")


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

    async def test_show_values_only_after_validation(self):
        settings = {"device_id": "123456789012", "identity": "hidden@example.com",
                    "unlock_secret": "secret-not-for-output"}
        snapshot = {"health": "ok", "device_id": settings["device_id"]}
        readings = {"supply_air": 19.7, "outdoor_air": -1.2,
                    "exhaust_air": 23.0, "extract_air": 21.5,
                    "humidity": 47.0}
        fake = AsyncMock()
        fake.poll_once.return_value = snapshot
        with patch.object(live_once, "SDKSnapshotAdapter", return_value=fake), \
             patch.object(live_once, "parse_snapshot", return_value=readings), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            await live_once.read_once(settings, show_values=True)
        lines = output.getvalue().splitlines()
        self.assertEqual(lines[0], "PASS: one read-only RPC45 snapshot validated")
        self.assertEqual(lines[1], "READINGS_BEGIN")
        self.assertEqual(lines[2], "VALUE supply_air: 19.7 °C")
        self.assertEqual(lines[3], "VALUE outdoor_air: -1.2 °C")
        self.assertEqual(lines[4], "VALUE exhaust_air: 23.0 °C")
        self.assertEqual(lines[5], "VALUE extract_air: 21.5 °C")
        self.assertEqual(lines[6], "VALUE humidity: 47 %")
        self.assertEqual(lines[7], "READINGS_END")
        self.assertEqual(len(lines), 8)
        self.assertNotIn("123456789012", output.getvalue())
        self.assertNotIn("hidden@example.com", output.getvalue())
        self.assertNotIn("secret-not-for-output", output.getvalue())
        fake.poll_once.assert_awaited_once()

    async def test_invalid_snapshot_never_shows_values(self):
        settings = {"device_id": "123456789012", "identity": "hidden@example.com",
                    "unlock_secret": "secret-not-for-output"}
        fake = AsyncMock()
        fake.poll_once.return_value = {"invalid": True}
        with patch.object(live_once, "SDKSnapshotAdapter", return_value=fake), \
             patch.object(live_once, "parse_snapshot", side_effect=ValueError("invalid")), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            with self.assertRaises(ValueError):
                await live_once.read_once(settings, show_values=True)
        self.assertEqual(output.getvalue(), "")
        fake.poll_once.assert_awaited_once()

    async def test_default_hides_all_values(self):
        settings = {"device_id": "123456789012", "identity": "hidden@example.com",
                    "unlock_secret": "secret-not-for-output"}
        fake = AsyncMock()
        fake.poll_once.return_value = {"health": "ok"}
        readings = {"supply_air": 19.7, "outdoor_air": -1.2,
                    "exhaust_air": 23.0, "extract_air": 21.5,
                    "humidity": 47.0}
        with patch.object(live_once, "SDKSnapshotAdapter", return_value=fake), \
             patch.object(live_once, "parse_snapshot", return_value=readings), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            await live_once.read_once(settings)
        self.assertNotIn("VALUE ", output.getvalue())
        self.assertNotIn("READINGS_BEGIN", output.getvalue())
        fake.poll_once.assert_awaited_once()

    async def test_incomplete_formatted_values_never_claim_success(self):
        settings = {"device_id": "123456789012", "identity": "a", "unlock_secret": "b"}
        fake = AsyncMock()
        fake.poll_once.return_value = {"health": "ok"}
        with patch.object(live_once, "SDKSnapshotAdapter", return_value=fake), \
             patch.object(live_once, "parse_snapshot", return_value={"supply_air": 19.7}), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            with self.assertRaises(KeyError):
                await live_once.read_once(settings, show_values=True)
        self.assertEqual(output.getvalue(), "")
        fake.poll_once.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
