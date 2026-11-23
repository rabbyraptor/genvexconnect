"""Offline safety tests for one 12-candidate RPC45 batch; no SDK or network."""
import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "probe_optima270_all_source_candidates_batch.py"
RUNNER = ROOT / "scripts" / "run_optima270_all_candidates_batch_from_deck.sh"
SPEC = importlib.util.spec_from_file_location("batch_probe_2b", SCRIPT)
probe = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = probe
SPEC.loader.exec_module(probe)


class TwelveBatchSafetyTests(unittest.TestCase):
    def test_fixed_source_candidates_only(self):
        cs = probe.selected_candidates()
        self.assertEqual(len(cs), 12)
        self.assertEqual(len({c.address for c in cs}), 12)
        body = probe.request_body(cs)
        self.assertEqual(body["request"]["trailer"], 1)
        self.assertEqual(
            body["request"]["datapoints"],
            [{"obj": 0, "address": c.address} for c in cs],
        )
        with self.assertRaises(ValueError):
            probe.request_body(cs[:-1])
        with self.assertRaises(ValueError):
            probe.request_body(tuple(reversed(cs)))

    def test_default_inert_and_live_gate(self):
        with patch.object(probe, "execute_one_batch", side_effect=AssertionError("SDK invoked")), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(probe.main([]), 0)
        self.assertIn("OFFLINE preview", out.getvalue())
        for flags in (
            ["--execute-live"],
            ["--approved-read-only"],
            ["--passphrase-stdin"],
            ["--execute-live", "--approved-read-only"],
        ):
            with self.subTest(flags=flags), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as err:
                    probe.main(flags)
                self.assertEqual(err.exception.code, 2)

    def test_explicit_approval_calls_one_batch_once(self):
        calls = []
        def fake(cs, *, use_passphrase_stdin=False):
            calls.append((cs, use_passphrase_stdin))
        with patch.object(probe, "execute_one_batch", side_effect=fake), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(probe.main([
                "--execute-live", "--approved-read-only", "--passphrase-stdin"
            ]), 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0][0]), 12)
        self.assertTrue(calls[0][1])

    def test_strict_response_count_and_types(self):
        import json
        ok = json.dumps({"response": {"values": [{"value": i} for i in range(12)]}})
        self.assertEqual(probe.decode_batch_response(ok), tuple(range(12)))
        for bad in (
            "{}",
            json.dumps({"response": {"values": [{"value": i} for i in range(11)]}}),
            json.dumps({"response": {"values": [{"value": i} for i in range(13)]}}),
            json.dumps({"response": {"values": [{"value": True}] * 12}}),
            json.dumps({"response": {"values": [{"value": 32768}] * 12}}),
            json.dumps({"response": {"values": [{"value": "0"}] * 12}}),
            "bad json",
            ok + " " * 17000,
        ):
            with self.subTest(bad=bad[:32]), self.assertRaises(ValueError):
                probe.decode_batch_response(bad)

    def test_only_read_only_rpc_and_single_invoke(self):
        source = SCRIPT.read_text()
        self.assertIn('id="45"', probe.READ_ONLY_XML.decode())
        self.assertNotIn('id="43"', probe.READ_ONLY_XML.decode())
        self.assertNotIn('id="42"', probe.READ_ONLY_XML.decode())
        self.assertEqual(source.count("status = invoke(session,"), 1)
        self.assertNotIn("nabtoRpcInvoke", RUNNER.read_text())

    def test_runner_preflight_and_host_gate(self):
        result = subprocess.run(["bash", "-n", str(RUNNER)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run(["bash", str(RUNNER), "--preflight"],
                                capture_output=True, text=True, input="", timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OFFLINE preview", result.stdout)
        source = RUNNER.read_text()
        self.assertIn('read -r -p "Nabto-identitet (e-mail; synlig): "', source)
        self.assertIn('read -r -p "Genvex device-ID (12 cifre; synligt): "', source)
        self.assertIn('export GENVEX_NABTO_HOST="${DEVICE_ID}.remote.lscontrol.dk"', source)
        self.assertIn('[[ ! "$DEVICE_ID" =~ ^[0-9]{12}$ ]]', source)
        self.assertNotIn('KNOWN_HOST', source)
        self.assertIn('read -r -s -p "Nøgleadgangskode (skjult): "', source)
        self.assertLess(source.index('export GENVEX_NABTO_HOST='),
                        source.index('IFS= read -r -s -p "Nøgleadgangskode'))
        self.assertEqual(source.count('timeout -k 5s 90s'), 1)


if __name__ == "__main__":
    unittest.main()
