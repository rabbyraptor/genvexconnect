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
from sdk_snapshot_adapter import classify_probe_failure, parse_rpc_diagnostics, parse_rpc_events, parse_session_diagnostics, SDKSnapshotError


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
        with patch.object(sys, "argv", ["live_once.py"]), \
             patch.object(live_once, "read_settings", return_value=payload), \
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
            self.assertEqual(output.getvalue(), "BLOCKED: INPUT_INVALID\n")


class FailureClassificationTests(unittest.TestCase):
    def test_sdk_session_error(self):
        self.assertEqual(classify_probe_failure(
            b"SDK startup: 0\nResources: 0\nProfile session: 3\n"),
            "SDK_SESSION_FAILED")

    def test_numeric_session_status_only(self):
        self.assertEqual(parse_session_diagnostics(
            b"SDK startup: 0\nProfile session: 12\n"), 12)
        for bad in (
            b"Profile session: 1\nProfile session: 2\n",
            b"Profile session: 12 secret\n",
            b"Profile session: -1\n",
            b"Profile session: 99999999\n",
            b"Profile session: True\n",
            b"\xffProfile session: 8\n",
        ):
            with self.subTest(bad=bad):
                self.assertIsNone(parse_session_diagnostics(bad))
        self.assertIsNone(parse_session_diagnostics(b"SDK startup: 0\n"))

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


    def test_bounded_rpc_status_and_elapsed(self):
        self.assertEqual(parse_rpc_diagnostics(
            b"SDK startup: 0\nBatch RPC status: 5\nRPC elapsed_ms: 1432\n"),
            (5, 1432))

    def test_no_untrusted_text_or_ambiguous_markers(self):
        self.assertEqual(parse_rpc_diagnostics(
            b"Batch RPC status: 5 secret\nRPC elapsed_ms: 20\n"), (None, 20))
        self.assertEqual(parse_rpc_diagnostics(
            b"Batch RPC status: 5\nBatch RPC status: 6\nRPC elapsed_ms: 30\n"),
            (None, 30))
        self.assertEqual(parse_rpc_diagnostics(
            b"Batch RPC status: 99999999\nRPC elapsed_ms: -1\n"), (None, None))
        self.assertEqual(parse_rpc_diagnostics(
            b"Batch RPC status: 2\nRPC elapsed_ms: 99999999\n"), (2, None))
        self.assertEqual(parse_rpc_diagnostics(b"\xff\xfe"), (None, None))

    def test_rpc_events_allowlisted_from_redacted_probe_only(self):
        self.assertEqual(parse_rpc_events(
            b"Batch RPC status: 26\nDiagnostic: ('ERROR_JSON', [1000026])\n"),
            (1000026,))
        self.assertEqual(parse_rpc_events(
            b"Diagnostic: ('NO_JSON_DIAGNOSTIC', [])\n"), ())
        self.assertEqual(parse_rpc_events(
            b"Diagnostic: ('ERROR_JSON', [1000009, 1000026])\n"),
            (1000009, 1000026))

    def test_rpc_events_reject_malformed_or_untrusted_data(self):
        for value in (
            b"Diagnostic: ('ERROR_JSON', [1000026, 1000026])\n",
            b"Diagnostic: ('ERROR_JSON', [1000026])\nDiagnostic: ('ERROR_JSON', [1])\n",
            b"Diagnostic: ('ERROR_JSON', [True])\n",
            b"Diagnostic: ('ERROR_JSON', [-1])\n",
            b"Diagnostic: ('ERROR_JSON', [10000001])\n",
            b"Diagnostic: ('ERROR_JSON', ['secret'])\n",
            b"Diagnostic: __import__('os').system('false')\n",
            b"Diagnostic: ('ERROR_JSON', [1,2,3,4,5,6,7,8,9])\n",
            b"Diagnostic: ('ERROR_JSON', {'code': 1000026})\n",
        ):
            with self.subTest(value=value):
                self.assertEqual(parse_rpc_events(value), ())

    def test_diagnostic_failure_prints_only_allowlisted_numbers(self):
        payload = {"device_id": "123456789012", "identity": "private@example.com",
                   "unlock_secret": "sensitive"}
        error = SDKSnapshotError("SDK_RPC45_FAILED", rpc_status=5, elapsed_ms=1432, rpc_events=(1000026,))
        with patch.object(sys, "argv", ["live_once.py", "--diagnose"]), \
             patch.object(live_once, "read_settings", return_value=payload), \
             patch.object(live_once, "validate_private_profile"), \
             patch.object(live_once, "PROBE", Mock(is_file=lambda: True)), \
             patch.object(live_once, "read_once", new_callable=AsyncMock, side_effect=error), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(live_once.main(), 1)
        self.assertEqual(output.getvalue(),
                         "BLOCKED: SDK_RPC45_FAILED\n"
                         "DIAG RPC45_STATUS: 5\n"
                         "DIAG RPC45_ELAPSED_MS: 1432\n"
                         "DIAG RPC45_EVENTS: 1000026\n")
        self.assertNotIn("private@example.com", output.getvalue())
        self.assertNotIn("sensitive", output.getvalue())

    def test_session_diagnostic_prints_only_numeric_status(self):
        payload = {"device_id": "123456789012", "identity": "private@example.com",
                   "unlock_secret": "secret-value"}
        error = SDKSnapshotError("SDK_SESSION_FAILED", session_status=12)
        with patch.object(sys, "argv", ["live_once.py", "--diagnose"]), \
             patch.object(live_once, "read_settings", return_value=payload), \
             patch.object(live_once, "validate_private_profile"), \
             patch.object(live_once, "PROBE", Mock(is_file=lambda: True)), \
             patch.object(live_once, "read_once", new_callable=AsyncMock,
                          side_effect=error), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(live_once.main(), 1)
        self.assertIn("BLOCKED: SDK_SESSION_FAILED", output.getvalue())
        self.assertIn("DIAG SESSION_STATUS: 12", output.getvalue())
        self.assertNotIn("private@example.com", output.getvalue())
        self.assertNotIn("secret-value", output.getvalue())

    def test_diagnostic_unknown_values(self):
        payload = {"device_id": "123456789012", "identity": "a", "unlock_secret": "b"}
        error = SDKSnapshotError("SDK_RPC45_FAILED", rpc_status=-1, elapsed_ms=99999999)
        with patch.object(sys, "argv", ["live_once.py", "--diagnose"]), \
             patch.object(live_once, "read_settings", return_value=payload), \
             patch.object(live_once, "validate_private_profile"), \
             patch.object(live_once, "PROBE", Mock(is_file=lambda: True)), \
             patch.object(live_once, "read_once", new_callable=AsyncMock, side_effect=error), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(live_once.main(), 1)
        self.assertIn("DIAG RPC45_STATUS: unknown", output.getvalue())
        self.assertIn("DIAG RPC45_ELAPSED_MS: unknown", output.getvalue())
        self.assertIn("DIAG RPC45_EVENTS: none", output.getvalue())


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

    async def test_manual_recovery_resolves_only_one_validated_snapshot(self):
        settings = {"device_id": "123456789012", "identity": "private@example.com",
                    "unlock_secret": "hidden"}
        fake = AsyncMock()
        fake.poll_once.side_effect = [
            SDKSnapshotError("SDK_RPC45_FAILED", rpc_status=26,
                             rpc_events=(1000015,)),
            {"schema_version": 1},
        ]
        async def no_delay(_):
            return None
        with patch.object(live_once, "SDKSnapshotAdapter", return_value=fake), \
             patch.object(live_once.asyncio, "sleep", new=no_delay), \
             patch.object(live_once, "parse_snapshot", return_value={}), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            await live_once.read_once(settings, recover_once=True)
        self.assertEqual(fake.poll_once.await_count, 2)
        self.assertIn("RECOVERY: eligible RPC45 event", output.getvalue())
        self.assertEqual(output.getvalue().count("RECOVERY_RESULT: SUCCESS"), 1)
        self.assertIn("PASS: one read-only RPC45 snapshot validated", output.getvalue())
        self.assertNotIn("private@example.com", output.getvalue())
        self.assertNotIn("hidden", output.getvalue())

    async def test_manual_recovery_second_error_explicitly_fails(self):
        settings = {"device_id": "123456789012", "identity": "secret@example.com",
                    "unlock_secret": "secret-value"}
        fake = AsyncMock()
        fake.poll_once.side_effect = [
            SDKSnapshotError("SDK_RPC45_FAILED", rpc_status=26,
                             rpc_events=(1000015,)),
            SDKSnapshotError("SDK_RPC45_FAILED", rpc_status=26,
                             rpc_events=(1000015,)),
        ]
        async def no_delay(_):
            return None
        with patch.object(live_once, "SDKSnapshotAdapter", return_value=fake), \
             patch.object(live_once.asyncio, "sleep", new=no_delay), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            with self.assertRaises(SDKSnapshotError):
                await live_once.read_once(settings, recover_once=True)
        self.assertEqual(fake.poll_once.await_count, 2)
        self.assertIn("RECOVERY_RESULT: FAILED", output.getvalue())
        self.assertNotIn("RECOVERY_RESULT: SUCCESS", output.getvalue())
        self.assertNotIn("secret", output.getvalue())

    async def test_recovery_invalid_final_snapshot_never_reports_success(self):
        settings = {"device_id": "123456789012", "identity": "a",
                    "unlock_secret": "b"}
        fake = AsyncMock()
        fake.poll_once.side_effect = [
            SDKSnapshotError("SDK_RPC45_FAILED", rpc_status=26,
                             rpc_events=(1000015,)),
            {"not": "valid"},
        ]
        async def no_delay(_):
            return None
        with patch.object(live_once, "SDKSnapshotAdapter", return_value=fake), \
             patch.object(live_once.asyncio, "sleep", new=no_delay), \
             patch.object(live_once, "parse_snapshot",
                          side_effect=ValueError("secret-in-error")), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            with self.assertRaises(ValueError):
                await live_once.read_once(settings, recover_once=True)
        self.assertEqual(fake.poll_once.await_count, 2)
        self.assertIn("RECOVERY_RESULT: FAILED", output.getvalue())
        self.assertNotIn("PASS:", output.getvalue())
        self.assertNotIn("secret-in-error", output.getvalue())

    async def test_normal_success_does_not_claim_recovery(self):
        settings = {"device_id": "123456789012", "identity": "a",
                    "unlock_secret": "b"}
        fake = AsyncMock()
        fake.poll_once.return_value = {"schema_version": 1}
        with patch.object(live_once, "SDKSnapshotAdapter", return_value=fake), \
             patch.object(live_once, "parse_snapshot", return_value={}), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            await live_once.read_once(settings, recover_once=True)
        self.assertEqual(fake.poll_once.await_count, 1)
        self.assertNotIn("RECOVERY_RESULT:", output.getvalue())

    async def test_manual_recovery_does_not_retry_unrelated_error(self):
        settings = {"device_id": "123456789012", "identity": "x",
                    "unlock_secret": "y"}
        fake = AsyncMock()
        fake.poll_once.side_effect = SDKSnapshotError(
            "SDK_RPC45_FAILED", rpc_status=26, rpc_events=(1000026,)
        )
        with patch.object(live_once, "SDKSnapshotAdapter", return_value=fake), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            with self.assertRaises(SDKSnapshotError):
                await live_once.read_once(settings, recover_once=True)
        self.assertEqual(fake.poll_once.await_count, 1)
        self.assertEqual(output.getvalue(), "")

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
