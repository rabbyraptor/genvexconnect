"""Offline fake HTTP tests for the uninstalled v2 HA transport module."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys
import unittest

from test_snapshot import RuntimeUnavailable  # installs import-free dev_remote package
from test_runtime_client import _Session, _Response

SOURCE = Path(__file__).resolve().parents[1] / "custom_components/genvex_remote/runtime_client_v2_draft.py"
spec = importlib.util.spec_from_file_location("dev_remote.runtime_client_v2_draft", SOURCE)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
# Load the v2 snapshot parser in this package if not already imported.
PARSER = SOURCE.with_name("snapshot_v2_draft.py")
parser_spec = importlib.util.spec_from_file_location("dev_remote.snapshot_v2_draft", PARSER)
parser_module = importlib.util.module_from_spec(parser_spec)
sys.modules[parser_spec.name] = parser_module
parser_spec.loader.exec_module(parser_module)
spec.loader.exec_module(module)
V2Reader = module.V2AuthenticatedSnapshotReader


class V2ReaderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.device = "123456789012"
        self.token = "t" * 43
        self.endpoint = "http://local-genvex-nabto-remote:18275/v2/snapshot"
        self.doc = {
            "schema_version": 2, "device_id": self.device,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "health": "ok",
            "values": {
                "supply_air": 6.7, "outdoor_air": 0.4,
                "exhaust_air": 1.8, "extract_air": 7.8, "humidity": 67.0,
            },
            "optional": {"fan_duty": {
                "fan_duty_supply": 60.0, "fan_duty_extract": 58.0,
            }},
        }

    def reader(self, response):
        session = _Session(response)
        return V2Reader(session, endpoint=self.endpoint, token=self.token), session

    async def test_authorized_pinned_get_and_v2_values(self):
        reader, session = self.reader(_Response(body=json.dumps(self.doc).encode()))
        received = await reader.async_fetch_snapshot(self.device)
        self.assertEqual(received["optional"]["fan_duty"]["fan_duty_supply"], 60.0)
        self.assertEqual(session.url, self.endpoint)
        self.assertEqual(session.headers["Authorization"], "Bearer " + self.token)
        self.assertIs(session.allow_redirects, False)
        self.assertEqual(session.response.content.read_limits, [4097])

    async def test_empty_optional_is_available_base_not_false_zero(self):
        self.doc["optional"]["fan_duty"] = {}
        reader, _ = self.reader(_Response(body=json.dumps(self.doc).encode()))
        got = await reader.async_fetch_snapshot(self.device)
        self.assertEqual(got["optional"]["fan_duty"], {})
        self.assertEqual(got["values"]["humidity"], 67.0)

    async def test_reject_http_errors_and_redact_provider_body(self):
        reader, _ = self.reader(_Response(status=503, body=b"PRIVATE-ERROR"))
        with self.assertRaises(RuntimeUnavailable) as ctx:
            await reader.async_fetch_snapshot(self.device)
        self.assertNotIn("PRIVATE-ERROR", str(ctx.exception))
        self.assertNotIn(self.token, str(ctx.exception))

    async def test_invalid_devices_stale_or_partial_fans(self):
        for mode in ("wrong_id", "old", "partial", "unknown"):
            doc = json.loads(json.dumps(self.doc))
            if mode == "wrong_id":
                doc["device_id"] = "000000000000"
            elif mode == "old":
                doc["timestamp_utc"] = (datetime.now(timezone.utc) -
                                        timedelta(minutes=4)).isoformat()
            elif mode == "partial":
                del doc["optional"]["fan_duty"]["fan_duty_extract"]
            else:
                doc["secret"] = "SHOULD_NOT_LEAK"
            reader, _ = self.reader(_Response(body=json.dumps(doc).encode()))
            with self.subTest(mode=mode), self.assertRaises(RuntimeUnavailable):
                await reader.async_fetch_snapshot(self.device)

    async def test_oversize_content_length_and_non_dict(self):
        for response in (
            _Response(body=b"x" * 4097),
            _Response(body=b"[]"),
            _Response(body=b"{}", content_length=5000),
        ):
            reader, _ = self.reader(response)
            with self.assertRaises(RuntimeUnavailable):
                await reader.async_fetch_snapshot(self.device)

    def test_only_pinned_endpoint_allowed(self):
        for bad in (
            self.endpoint + "?token=abc",
            self.endpoint.replace("/v2/", "/v1/"),
            "https://attacker.example/v2/snapshot",
            "http://127.0.0.1:18275/v2/snapshot",
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                V2Reader(_Session(_Response()), endpoint=bad, token=self.token)


if __name__ == "__main__":
    unittest.main()
