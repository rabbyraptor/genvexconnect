"""Offline regression: RPC45 URL deduplication preserves exact DEV9 requests."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))

from persistent_rpc45_worker import rpc_url, raw_rpc_url, decode_batch
from raw_registers_v3 import BASE_ADDRESSES, OPTIONAL_ADDRESSES


class RPC45EncodingTests(unittest.TestCase):
    def _assert_request(self, url: bytes, addresses: tuple[int, ...]) -> None:
        self.assertIsInstance(url, bytes)
        prefix = b"nabto://123456789012.remote.lscontrol.dk/candidate_read_datapoints.json?json="
        self.assertTrue(url.startswith(prefix))
        data = json.loads(unquote(url[len(prefix):].decode("ascii")))
        self.assertEqual(data, {"request": {
            "datapoints": [{"obj": 0, "address": address} for address in addresses],
            "trailer": 1,
        }})
        # No whitespace in the exact encoded SDK query request.
        self.assertNotIn(b"%20", url)

    def test_baseline_wire_address_order(self) -> None:
        self.assertEqual(BASE_ADDRESSES, (20, 21, 22, 23, 26))
        self._assert_request(
            rpc_url("123456789012.remote.lscontrol.dk"), BASE_ADDRESSES,
        )

    def test_optional_wire_address_order(self) -> None:
        self.assertEqual(OPTIONAL_ADDRESSES, (
            24, 18, 19, 35, 36, 41, 42, 53, 40, 114, 115, 50,
        ))
        self._assert_request(
            raw_rpc_url("123456789012.remote.lscontrol.dk"), OPTIONAL_ADDRESSES,
        )

    def test_five_value_scaling_is_unchanged(self) -> None:
        response = json.dumps({"response": {"values": [
            {"value": 370}, {"value": 330}, {"value": 338},
            {"value": 374}, {"value": 64},
        ]}})
        self.assertEqual(decode_batch(response), {
            "supply_air": 7.0, "outdoor_air": 3.0,
            "exhaust_air": 3.8, "extract_air": 7.4, "humidity": 64.0,
        })
        self.assertIsNone(decode_batch('{"response":{"values":[]}}'))


if __name__ == "__main__":
    unittest.main()
