"""DEV8.3 installed-App offline regression for v3 raw IPC and worker."""
from __future__ import annotations

import asyncio
import ctypes as ct
from datetime import datetime, timezone
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1] / "runtime"
sys.path.insert(0, str(ROOT))

from test_dev3_persistent_adapter import FakeSDK
from raw_registers_v3 import (
    BASE_ADDRESSES, OPTIONAL_ADDRESSES, make_raw_v3, parse_raw_v3,
)
from raw_snapshot_state_v3 import RawV3SnapshotState
from snapshot_api import handle_read_request
from snapshot_api_v3 import handle_v3_read_request
from polling_http_server import SnapshotHTTPServer

DEVICE = "123456789012"
TOKEN = "T" * 43
BASE = (368, 308, 322, 378, 67)
EXTRA = (0, 6000, 5800, 2432, 2268, 0, 0, 0, 0, 0, 0, 10)


def new_snapshot(extra=EXTRA):
    return make_raw_v3(
        device_id=DEVICE, measured_at=datetime.now(timezone.utc),
        baseline_raw=BASE, additional_raw=extra,
    )


class _Poller:
    device_id = DEVICE

    def __init__(self, result):
        self.result = result

    async def poll_once(self):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class RawV3ServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_refresh_serves_v1_and_v3(self):
        provider = _Poller(new_snapshot())
        state = RawV3SnapshotState(provider)
        self.assertTrue(await state.refresh())
        legacy = state.current()
        expanded = state.current_v3()
        self.assertEqual(legacy["schema_version"], 1)
        self.assertEqual(set(legacy["values"]), {
            "supply_air", "outdoor_air", "exhaust_air", "extract_air", "humidity"
        })
        self.assertEqual(expanded["schema_version"], 3)
        self.assertEqual(len(parse_raw_v3(
            expanded, expected_device_id=DEVICE,
        )[1]), 17)
        request = dict(
            method="GET", authorization="Bearer " + TOKEN,
            expected_token=TOKEN, device_id=DEVICE,
        )
        status, body = handle_read_request(
            **request, path="/v1/snapshot", snapshot=legacy,
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["schema_version"], 1)
        status, body = handle_v3_read_request(
            **request, path="/v3/snapshot", snapshot=expanded,
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["optional"]["raw_registers"]), 12)
        self.assertEqual(handle_v3_read_request(
            **(request | {"authorization": None}),
            path="/v3/snapshot", snapshot=expanded,
        )[0], 401)
        self.assertEqual(handle_v3_read_request(
            **request, path="/v4/snapshot", snapshot=expanded,
        )[0], 404)
        self.assertEqual(handle_v3_read_request(
            **request, path="/v3/snapshot",
            snapshot=(expanded | {"private_identity": "SECRET"}),
        )[0], 503)

    async def test_failed_optional_poll_keeps_baseline_and_marks_missing(self):
        provider = _Poller(new_snapshot())
        state = RawV3SnapshotState(provider)
        self.assertTrue(await state.refresh())
        provider.result = new_snapshot(None)
        self.assertTrue(await state.refresh())
        self.assertIsNotNone(state.current())
        self.assertEqual(state.current_v3()["optional"]["raw_registers"], {})
        provider.result = RuntimeError("SENSITIVE_WORKER_ERROR")
        self.assertFalse(await state.refresh())
        self.assertIsNone(state.current())
        self.assertIsNone(state.current_v3())

    async def test_v3_result_is_detached_from_mutations(self):
        state = RawV3SnapshotState(_Poller(new_snapshot()))
        self.assertTrue(await state.refresh())
        copied = state.current_v3()
        copied["raw_values"]["humidity"] = -123
        copied["optional"]["raw_registers"]["rotor_rpm"] = -999
        self.assertEqual(state.current_v3()["raw_values"]["humidity"], 67)
        self.assertEqual(
            state.current_v3()["optional"]["raw_registers"]["rotor_rpm"], 10
        )


class _RawFakeSDK(FakeSDK):
    def __init__(self):
        self.requests = []
        self.optional_calls = 0
        super().__init__()

    def invoke(self, _session, url, pointer):
        import ctypes
        query = unquote(url.decode().split("?json=", 1)[1])
        doc = json.loads(query)
        addresses = tuple(
            row["address"] for row in doc["request"]["datapoints"]
        )
        self.requests.append(addresses)
        self.events.append("invoke")
        if addresses == OPTIONAL_ADDRESSES:
            self.optional_calls += 1
            if self.optional_calls == 2:
                return 26
            raw = EXTRA
        elif addresses == BASE_ADDRESSES:
            raw = BASE
        else:
            raise AssertionError("Unapproved RPC address set")
        body = json.dumps({
            "response": {"values": [{"value": value} for value in raw]}
        }).encode()
        buffer = ctypes.create_string_buffer(body)
        self.buffers.append(buffer)
        ctypes.cast(pointer, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.cast(
            buffer, ctypes.c_void_p
        )
        return 0


class RawV3WorkerTests(unittest.TestCase):
    def test_persistent_worker_serializes_baseline_and_raw_with_optional_failure(self):
        spec = importlib.util.spec_from_file_location(
            "worker_dev8_raw_v3", ROOT / "persistent_rpc45_worker.py",
        )
        worker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(worker)
        fake = _RawFakeSDK()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "client.crt").write_text("test")
            (root / "client-encrypted.key").write_text("test")
            config = json.dumps({
                "identity": "test@example.invalid",
                "host": DEVICE + ".remote.lscontrol.dk",
                "passphrase": "fake-passphrase",
            })
            commands = "POLL3\nPOLL3\nPOLL\nCLOSE\n"
            stdin = io.TextIOWrapper(
                io.BytesIO((config + "\n" + commands).encode())
            )
            stdout = io.StringIO()
            with patch.object(worker.ct, "CDLL", return_value=fake), \
                 patch.object(sys, "stdin", stdin), \
                 patch.object(sys, "stdout", stdout), \
                 patch.object(sys, "argv", ["worker", "--serve-stdio"]), \
                 patch.dict(os.environ, {"GENVEX_NABTO_PROFILE": tmp}):
                self.assertEqual(worker.main(), 0)
        lines = stdout.getvalue().splitlines()
        self.assertEqual(len(lines), 4)
        self.assertIn("GENVEX_PERSISTENT_READY=", lines[0])
        frames = [json.loads(line.split("=", 1)[1]) for line in lines[1:]]
        self.assertTrue(all(f["ok"] for f in frames))
        self.assertEqual(
            [f["snapshot"]["schema_version"] for f in frames],
            [3, 3, 1],
        )
        self.assertEqual(
            len(frames[0]["snapshot"]["optional"]["raw_registers"]), 12
        )
        self.assertEqual(frames[1]["snapshot"]["optional"]["raw_registers"], {})
        self.assertEqual(frames[2]["snapshot"]["values"]["supply_air"], 6.8)
        self.assertEqual(
            fake.requests,
            [BASE_ADDRESSES, OPTIONAL_ADDRESSES,
             BASE_ADDRESSES, OPTIONAL_ADDRESSES, BASE_ADDRESSES],
        )
        self.assertNotIn("fake-passphrase", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
