"""SDK-free regressions for isolated v2 QEMU snapshot marker and lifecycle.

Only launches local Python snippets using fake credentials and synthetic readings.
Never imports the real v2 probe, Nabto SDK, or opens network sessions.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

from polling_service import PollingService
from sdk_snapshot_adapter import SDKSnapshotError
from sdk_snapshot_adapter_v2 import (
    SDKSnapshotV2Adapter, parse_v2_probe_output,
)
from v2_polling_state import V2SnapshotState


DEVICE = "123456789012"
ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "experimental/genvex_remote/probe_remote_snapshot_v2.py"

FAKE_SUBPROCESS = r'''
import json, sys
from datetime import datetime, timezone
lines = [sys.stdin.readline().strip() for _ in range(3)]
if lines != ["mock_user", "123456789012.remote.lscontrol.dk", "mock_secret"]:
    raise SystemExit(7)
payload = {
    "schema_version": 2, "device_id": "123456789012",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(), "health": "ok",
    "values": {"supply_air": 6.8, "outdoor_air": 0.8,
               "exhaust_air": 2.2, "extract_air": 7.8, "humidity": 67.0},
    "optional": {"fan_duty": {
        "fan_duty_supply": 60.0, "fan_duty_extract": 58.0,
    }},
}
print("GENVEX_READONLY_SNAPSHOT_V2=" + json.dumps(payload))
'''


def sample():
    return {
        "schema_version": 2,
        "device_id": DEVICE,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "health": "ok",
        "values": {
            "supply_air": 6.8, "outdoor_air": 0.8,
            "exhaust_air": 2.2, "extract_air": 7.8, "humidity": 67.0,
        },
        "optional": {"fan_duty": {
            "fan_duty_supply": 60.0, "fan_duty_extract": 58.0,
        }},
    }


def encode(payload):
    return ("Diagnostic: no secrets\nGENVEX_READONLY_SNAPSHOT_V2="
            + json.dumps(payload) + "\n").encode()


class V2SDKAdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        folder = Path(tmp.name)
        self.probe = folder / "fake-probe.py"
        self.probe.write_text("# not run by any test\n", encoding="utf-8")
        self.profile = str(folder)

    def adapter(self, snippet=FAKE_SUBPROCESS, timeout=2):
        return SDKSnapshotV2Adapter(
            device_id=DEVICE, identity="mock_user",
            unlock_secret="mock_secret", profile_dir=self.profile,
            probe_file=str(self.probe), timeout_seconds=timeout,
            command=(sys.executable, "-c", snippet),
        )

    async def test_real_python_subprocess_mock_returns_v2(self):
        payload = await self.adapter().poll_once()
        self.assertEqual(payload["values"]["supply_air"], 6.8)
        self.assertEqual(payload["optional"]["fan_duty"], {
            "fan_duty_supply": 60.0,
            "fan_duty_extract": 58.0,
        })

    async def test_v2_adapter_integrates_with_state_and_service(self):
        state = V2SnapshotState(self.adapter())
        service = PollingService(state, interval_seconds=60)
        await service.start()
        try:
            for _ in range(150):
                if state.current() is not None:
                    break
                await asyncio.sleep(0.02)
            self.assertEqual(state.current()["values"]["humidity"], 67.0)
        finally:
            await service.stop()
        self.assertIsNone(state.current())

    def test_exact_one_marker_and_optional_empty(self):
        payload = sample()
        payload["optional"]["fan_duty"] = {}
        self.assertEqual(
            parse_v2_probe_output(encode(payload), device_id=DEVICE),
            payload,
        )

    def test_bad_marker_shapes_redacted(self):
        valid = encode(sample())
        for raw in (
            b"no marker", valid + valid, b"GENVEX_READONLY_SNAPSHOT_V2={}",
            b"GENVEX_READONLY_SNAPSHOT={}\n", b"\xff",
            valid + b"x" * 33000,
        ):
            with self.subTest(size=len(raw)), self.assertRaises(
                SDKSnapshotError
            ) as ctx:
                parse_v2_probe_output(raw, device_id=DEVICE)
            self.assertNotIn("mock_secret", str(ctx.exception))

    def test_wrong_device_stale_partial_and_invalid_fan_fail_closed(self):
        for name in ("wrong", "stale", "partial", "bad", "extra", "missing"):
            payload = sample()
            if name == "wrong":
                payload["device_id"] = "000000000000"
            elif name == "stale":
                payload["timestamp_utc"] = (
                    datetime.now(timezone.utc) - timedelta(minutes=5)
                ).isoformat()
            elif name == "partial":
                del payload["optional"]["fan_duty"]["fan_duty_extract"]
            elif name == "bad":
                payload["optional"]["fan_duty"]["fan_duty_supply"] = 101
            elif name == "extra":
                payload["credentials"] = "MUST_NOT_LEAK"
            elif name == "missing":
                del payload["values"]["humidity"]
            with self.subTest(name=name), self.assertRaises(SDKSnapshotError):
                parse_v2_probe_output(encode(payload), device_id=DEVICE)

    async def test_nonzero_exit_and_output_do_not_leak(self):
        adapter = self.adapter(
            'import sys; print("PRIVATE-MESSAGE"); sys.exit(2)'
        )
        with self.assertRaises(SDKSnapshotError) as ctx:
            await adapter.poll_once()
        self.assertNotIn("PRIVATE-MESSAGE", str(ctx.exception))

    async def test_bounded_timeout_and_cancel(self):
        blocked = 'import time; time.sleep(30)'
        with self.assertRaises(SDKSnapshotError):
            await self.adapter(blocked, timeout=1).poll_once()
        task = asyncio.create_task(self.adapter(blocked, timeout=60).poll_once())
        await asyncio.sleep(0.1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)

    def test_probe_source_only_one_rpc45_and_exact_seven(self):
        text = PROBE.read_text(encoding="utf-8")
        self.assertEqual(text.count("status = invoke(session,"), 1)
        self.assertIn('id="45"', text)
        self.assertNotIn('id="43"', text)
        self.assertNotIn('id="42"', text)
        self.assertIn('(18, "Supply fan duty", 100, 0, "%")', text)
        self.assertIn('(19, "Extract fan duty", 100, 0, "%")', text)
        self.assertIn("GENVEX_READONLY_SNAPSHOT_V2=", text)
        self.assertNotIn('print("GENVEX_READONLY_SNAPSHOT="', text)
        self.assertIn('if "--settings-stdin" in sys.argv:', text)
        self.assertIn('len(values) != len(SENSORS)', text)
        self.assertIn('if 0 <= readings[5] <= 10000 and 0 <= readings[6] <= 10000:', text)


if __name__ == "__main__":
    unittest.main()
