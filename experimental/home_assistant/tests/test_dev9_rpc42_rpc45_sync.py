"""Offline checks for bracketed RPC42/RPC45 fan-state probe."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest
from urllib.parse import parse_qs, urlsplit

FILE = Path(__file__).resolve().parents[3] / "scripts/probe_rpc42_rpc45_sync_readonly.py"
spec = importlib.util.spec_from_file_location("sync_probe", FILE)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class SynchronizedFanReadTests(unittest.TestCase):
    def test_only_read_only_query_ids_and_expected_types(self):
        combined = probe.xml_interface()
        self.assertIn(b'id="42"', combined)
        self.assertIn(b'id="45"', combined)
        self.assertNotIn(b'id="43"', combined)
        self.assertEqual(probe.REGISTERS, (18, 19, 35, 36))

    def test_rpc42_and_rpc45_request_address_order(self):
        for query, addresses, key in (
            (42, [7], "setpoints"),
            (45, [18, 19, 35, 36], "datapoints"),
        ):
            with self.subTest(query=query):
                url = probe.request_url(
                    "123456789012.remote.lscontrol.dk", query
                ).decode()
                request = json.loads(parse_qs(urlsplit(url).query)["json"][0])
                self.assertEqual(
                    [item["address"] for item in request["request"][key]],
                    addresses,
                )
                self.assertTrue(all(
                    item["obj"] == 0 for item in request["request"][key]
                ))
                self.assertEqual(request["request"]["trailer"], 1)

    def test_read_only_decode_and_zero_is_a_valid_fan_level(self):
        self.assertEqual(probe.decode(42, json.dumps({
            "response": {"prefix_unknown": 0, "values": [{"value": 0}]}
        })), 0)
        self.assertEqual(probe.decode(45, json.dumps({
            "response": {"values": [
                {"value": 2000}, {"value": 1800},
                {"value": 792}, {"value": 692},
            ]}
        })), {18: 2000, 19: 1800, 35: 792, 36: 692})

    def test_reject_malformed_reply_and_unknown_query(self):
        for value in (-1, 5, 65536, "0", True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    probe.decode(42, json.dumps({
                        "response": {
                            "prefix_unknown": 0,
                            "values": [{"value": value}],
                        }
                    }))
        for data in (
            {"response": {"values": [{"value": 0}]}},
            {"response": {"prefix_unknown": 0, "values": []}},
        ):
            with self.assertRaises((ValueError, KeyError)):
                probe.decode(42, json.dumps(data))
        with self.assertRaises(ValueError):
            probe.request_url("123.remote.lscontrol.dk", 43)

    def test_session_order_and_intervals(self):
        source = FILE.read_text(encoding="utf-8")
        self.assertIn("for query in (42, 45, 42):", source)
        self.assertIn("before == after", source)
        self.assertIn("time.monotonic()", source)
        self.assertNotIn("nabtoRpcWrite", source)


if __name__ == "__main__":
    unittest.main()
