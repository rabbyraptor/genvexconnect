"""Safety tests for opt-in legacy one-candidate probe, entirely OFFLINE."""
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "probe_optima270_single_source_candidate.py"
SPEC = importlib.util.spec_from_file_location("candidate_probe_offline_test", SCRIPT)
probe = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = probe
SPEC.loader.exec_module(probe)


class OneCandidateProbeSafetyTests(unittest.TestCase):
    def test_default_is_inert_preview(self):
        printed = io.StringIO()
        with patch.object(probe, "execute_one_read", side_effect=AssertionError("Called live SDK")), \
             contextlib.redirect_stdout(printed):
            self.assertEqual(probe.main(["--key", "frost_protection_temp"]), 0)
        self.assertIn("OFFLINE preview", printed.getvalue())
        self.assertIn("address: 24", printed.getvalue())

    def test_live_requires_both_flags(self):
        with patch.object(probe, "execute_one_read", side_effect=AssertionError("Called live SDK")), \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                probe.main(["--key", "fan_rpm_supply", "--execute-live"])
        self.assertEqual(ctx.exception.code, 2)

    def test_approval_without_live_is_not_a_read(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                probe.main(["--key", "fan_rpm_supply", "--approved-read-only"])

    def test_explicit_flags_allow_exactly_one_selected_candidate(self):
        seen = []
        def fake_execute(candidate, *, use_passphrase_stdin=False):
            seen.append((candidate, use_passphrase_stdin))
        with patch.object(probe, "execute_one_read", side_effect=fake_execute), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(probe.main([
                "--key", "fan_rpm_supply", "--execute-live",
                "--approved-read-only", "--passphrase-stdin"
            ]), 0)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][0].address, 35)
        self.assertTrue(seen[0][1])

    def test_live_without_piped_passphrase_fails_before_any_sdk_work(self):
        with patch.object(probe, "execute_one_read", side_effect=AssertionError("Called live SDK")), \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                probe.main(["--key", "frost_protection_temp", "--execute-live", "--approved-read-only"])
        self.assertEqual(ctx.exception.code, 2)

    def test_piped_passphrase_flag_not_allowed_offline(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                probe.main(["--key", "frost_protection_temp", "--passphrase-stdin"])
        self.assertEqual(ctx.exception.code, 2)

    def test_can_only_select_a_source_defined_single_candidate(self):
        for key in ("supply_air", "unknown", "all", "35", "", "alarm"):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    probe.select_candidate(key)
        candidate = probe.select_candidate("bypass_analog_raw")
        self.assertEqual(probe.request_body(candidate), {
            "request": {"datapoints": [{"obj": 0, "address": 40}], "trailer": 1}
        })

    def test_invalid_cli_candidate_fails_without_live_access(self):
        with patch.object(probe, "execute_one_read", side_effect=AssertionError("Live called")), \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                probe.main(["--key", "unknown"])
        self.assertEqual(ctx.exception.code, 2)

    def test_reject_tampered_candidate_object(self):
        from optima270_source_only import SourceOnlyDatapoint
        forged = SourceOnlyDatapoint("frost_protection_temp", "fake", 999)
        with self.assertRaises(ValueError):
            probe.request_body(forged)

    def test_xml_contains_only_verified_read_only_rpc_shape(self):
        xml = probe.READ_ONLY_XML.decode()
        self.assertEqual(xml.count('<query name="'), 1)
        self.assertIn('id="45"', xml)
        self.assertNotIn('id="43"', xml)
        self.assertNotIn('id="42"', xml)
        self.assertNotIn("write", xml.lower())

    def test_bounded_json_response_must_be_exactly_one_int16(self):
        ok = '{"response":{"values":[{"value":365}]}}'
        self.assertEqual(probe.decode_single_response(ok), 365)
        for bad in (
            "{}",
            '{"response":{"values":[]}}',
            '{"response":{"values":[{"value":3},{"value":4}]}}',
            '{"response":{"values":[{"value":true}]}}',
            '{"response":{"values":[{"value":1.5}]}}',
            '{"response":{"values":[{"value":32768}]}}',
            '{"response":{"values":[{"value":"12"}]}}',
            '{"response":{"values":[{"value":5}]}}' + (" " * 9000),
            "not json",
        ):
            with self.subTest(bad=bad[:60]):
                with self.assertRaises(ValueError):
                    probe.decode_single_response(bad)

    def test_opaque_error_codes_only(self):
        raw = '{"error":{"event":2000027,"message":"secret-email","code":3227}}'
        self.assertEqual(probe._status_events(raw), (3227, 2000027))
        self.assertEqual(probe._status_events("not json"), ())

    def test_profile_identity_is_sanitized(self):
        with self.assertRaises(ValueError):
            probe._check_existing_profile(Path("/tmp"), "bad/path@example.org")


if __name__ == "__main__":
    unittest.main()
