"""Offline-only regression checks for the seven-address guarded live test.

Never opens the SDK, network or HAOS runtime.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "probe_optima270_seven_snapshot_v2.py"
WRAPPER = ROOT / "scripts" / "run_optima270_seven_snapshot_v2_from_deck.sh"
spec = importlib.util.spec_from_file_location("seven_probe", SCRIPT)
probe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)


class SevenLiveProbeOfflineTests(unittest.TestCase):
    def test_no_sdk_by_default_and_exact_addresses(self):
        with patch.object(probe, "execute_one_batch", side_effect=AssertionError("Live")), \
             contextlib.redirect_stdout(io.StringIO()) as captured:
            self.assertEqual(probe.main([]), 0)
        self.assertIn("OFFLINE preview", captured.getvalue())
        self.assertIn("20,21,22,23,26,18,19", captured.getvalue())
        self.assertNotIn("GENVEX_READONLY_SNAPSHOT_V2=", captured.getvalue())

    def test_live_has_explicit_two_flag_gate(self):
        for args in (
            ["--execute-live"],
            ["--execute-live", "--passphrase-stdin"],
            ["--execute-live", "--approved-read-only"],
            ["--approved-read-only"],
        ):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as exc:
                    probe.main(args)
                self.assertEqual(exc.exception.code, 2)

    def test_live_calls_one_sdk_procedure_when_both_approvals_present(self):
        calls = []
        def fake(*, use_passphrase_stdin=False):
            calls.append(use_passphrase_stdin)
        with patch.object(probe, "execute_one_batch", side_effect=fake):
            self.assertEqual(probe.main([
                "--execute-live", "--approved-read-only", "--passphrase-stdin"
            ]), 0)
        self.assertEqual(calls, [True])

    def test_fixed_read_only_rpc_and_single_invoke(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('id="45"', probe.READ_ONLY_XML.decode())
        self.assertNotIn('id="43"', probe.READ_ONLY_XML.decode())
        self.assertEqual(source.count("status = invoke(session,"), 1)
        self.assertIn('request_body()', source)
        self.assertIn('GENVEX_READONLY_SNAPSHOT_V2=', source)
        self.assertLess(source.index('shutdown_status = shutdown()'),
                        source.index('GENVEX_READONLY_SNAPSHOT_V2='))
        self.assertNotIn("GENVEX_READONLY_SNAPSHOT=", source)

    def test_exact_seven_int16_response(self):
        import json
        good = json.dumps({"response": {"values": [
            {"value": v} for v in (367, 304, 318, 378, 67, 6000, 5800)
        ]}})
        self.assertEqual(probe.decode_batch_response(good),
                         (367, 304, 318, 378, 67, 6000, 5800))
        for bad in (
            '{"response":{"values":[]}}',
            '{"response":{"values":[{"value":1}]}}',
            '{"response":{"values":[{"value":1},{"value":2},{"value":3},{"value":4},{"value":5},{"value":6},{"value":7},{"value":8}]}}',
            '{"response":{"values":[{"value":true}]}}',
            "{}",
            good + " " * 17000,
        ):
            with self.subTest(bad=bad[:40]), self.assertRaises(ValueError):
                probe.decode_batch_response(bad)

    def test_wrapper_preflight_and_prompt_safety(self):
        check = subprocess.run(
            ["bash", "-n", str(WRAPPER)], capture_output=True, text=True, timeout=10
        )
        self.assertEqual(check.returncode, 0, check.stderr)
        check = subprocess.run(
            ["bash", str(WRAPPER), "--preflight"],
            capture_output=True, text=True, input="", timeout=15,
        )
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertIn("OFFLINE preview", check.stdout)
        source = WRAPPER.read_text(encoding="utf-8")
        self.assertIn('export GENVEX_NABTO_HOST="${DEVICE_ID}.remote.lscontrol.dk"', source)
        self.assertIn('[[ ! "$DEVICE_ID" =~ ^[0-9]{12}$ ]]', source)
        self.assertIn('read -r -p "Nabto-identitet (e-mail; synlig): "', source)
        self.assertIn('read -r -p "Genvex device-ID (12 cifre; synligt): "', source)
        self.assertIn('read -r -s -p "Nøgleadgangskode (skjult): "', source)
        self.assertEqual(source.count("timeout -k 5s 90s"), 1)
        self.assertNotIn("KNOWN_HOST", source)


if __name__ == "__main__":
    unittest.main()
