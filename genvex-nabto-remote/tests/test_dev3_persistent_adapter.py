"""SDK-free subprocess, recovery, and native-call protocol tests.

Uses only local Python children and a fake ctypes SDK, no real gateway,
network, credentials, QEMU or Home Assistant runtime.
"""
from __future__ import annotations

import asyncio
import ctypes as ct
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "runtime"
sys.path.insert(0, str(ROOT))

from persistent_sdk_adapter import PersistentSDKSnapshotAdapter
from sdk_snapshot_adapter import SDKSnapshotError
from snapshot_state import SnapshotState

DEVICE = "123456789012"
CHILD = r"""
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

mode, logpath = sys.argv[1:3]
data = json.loads(sys.stdin.buffer.readline())
assert data["identity"] == "test@example.invalid"
assert data["passphrase"] == "fixture-secret"
log = Path(logpath)
with log.open("a") as output:
    output.write("started:" + str(os.getpid()) + "\n")
if mode == "startup-error":
    print('GENVEX_PERSISTENT_READY={"ok":false,"stage":"SDK_SESSION_FAILED"}', flush=True)
    sys.exit(1)
print('GENVEX_PERSISTENT_READY={"ok":true}', flush=True)
index = 0
while True:
    command = sys.stdin.buffer.readline()
    if command == b"CLOSE\n" or not command:
        break
    if command != b"POLL\n":
        sys.exit(2)
    index += 1
    with log.open("a") as output:
        output.write("poll:" + str(os.getpid()) + "\n")
    if mode == "hang":
        time.sleep(30)
    if mode == "oversize":
        print("X" * 9000, flush=True)
        continue
    device = "999999999999" if mode == "wrong-device" else "123456789012"
    if (mode == "error-recover" and index == 2
            or mode == "twice" and index in (2, 3)):
        print('GENVEX_PERSISTENT_RESULT={"ok":false,"status":26,"elapsed_ms":13000}', flush=True)
        continue
    message = {"ok": True, "snapshot": {
        "schema_version": 1, "device_id": device,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "health": "ok",
        "values": {
            "supply_air": 7.1, "outdoor_air": 3.5,
            "exhaust_air": 4.4, "extract_air": 7.9, "humidity": 66.0,
        },
    }}
    print("GENVEX_PERSISTENT_RESULT=" + json.dumps(message), flush=True)
    if mode == "exit-after-first" and index == 1:
        break
with log.open("a") as output:
    output.write("closed:" + str(os.getpid()) + "\n")
"""


class PersistentAdapterTests(unittest.IsolatedAsyncioTestCase):
    def new_adapter(self, tmp, mode, *, timeout=2):
        worker = Path(tmp) / "worker.py"
        worker.write_text("# local fixture\n")
        log = Path(tmp) / "events.txt"
        adapter = PersistentSDKSnapshotAdapter(
            device_id=DEVICE, identity="test@example.invalid",
            unlock_secret="fixture-secret", profile_dir=tmp,
            worker_file=str(worker), timeout_seconds=timeout,
            startup_timeout_seconds=2,
            command=(sys.executable, "-u", "-c", CHILD, mode, str(log)),
        )
        return adapter, log

    async def test_one_session_survives_status26_and_recovers(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter, log = self.new_adapter(tmp, "error-recover")
            try:
                one = await adapter.poll_once()
                pid = adapter._proc.pid
                self.assertEqual(one["values"]["humidity"], 66.0)
                with self.assertRaises(SDKSnapshotError) as caught:
                    await adapter.poll_once()
                self.assertEqual(caught.exception.code, "SDK_RPC45_FAILED")
                self.assertEqual(caught.exception.rpc_status, 26)
                self.assertEqual(adapter._proc.pid, pid)
                recovered = await adapter.poll_once()
                self.assertEqual(recovered["device_id"], DEVICE)
                self.assertEqual(adapter._proc.pid, pid)
                self.assertEqual(adapter._consecutive_rpc_errors, 0)
            finally:
                await adapter.aclose()
            lines = log.read_text().splitlines()
            self.assertEqual(sum(x.startswith("started:") for x in lines), 1)
            self.assertEqual(sum(x.startswith("poll:") for x in lines), 3)
            self.assertEqual(sum(x.startswith("closed:") for x in lines), 1)

    async def test_snapshot_state_unavailable_then_same_session_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter, _ = self.new_adapter(tmp, "error-recover")
            state = SnapshotState(adapter)
            try:
                self.assertTrue(await state.refresh())
                self.assertEqual(len(state.current()["values"]), 5)
                self.assertFalse(await state.refresh())
                self.assertIsNone(state.current())
                self.assertTrue(await state.refresh())
                self.assertEqual(len(state.current()["values"]), 5)
            finally:
                await adapter.aclose()

    async def test_two_consecutive_rpc_errors_recycle_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter, log = self.new_adapter(tmp, "twice")
            try:
                await adapter.poll_once()
                for index in range(2):
                    with self.assertRaises(SDKSnapshotError):
                        await adapter.poll_once()
                    self.assertEqual(adapter._proc is None, index == 1)
                self.assertEqual((await adapter.poll_once())["values"]["humidity"], 66.0)
            finally:
                await adapter.aclose()
            self.assertEqual(sum(x.startswith("started:") for x in log.read_text().splitlines()), 2)
            self.assertEqual(sum(x.startswith("closed:") for x in log.read_text().splitlines()), 2)

    async def test_single_flight_concurrent_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter, log = self.new_adapter(tmp, "ok")
            try:
                snapshots = await asyncio.gather(*(adapter.poll_once() for _ in range(5)))
                self.assertEqual(len(snapshots), 5)
                self.assertTrue(all(s["values"]["humidity"] == 66.0 for s in snapshots))
            finally:
                await adapter.aclose()
            self.assertEqual(sum(x.startswith("started:") for x in log.read_text().splitlines()), 1)
            self.assertEqual(sum(x.startswith("poll:") for x in log.read_text().splitlines()), 5)

    async def test_exited_worker_is_replaced_before_next_poll(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter, log = self.new_adapter(tmp, "exit-after-first")
            try:
                first = await adapter.poll_once()
                self.assertEqual(first["device_id"], DEVICE)
                original = adapter._proc
                await asyncio.wait_for(original.wait(), timeout=2)
                self.assertEqual(original.returncode, 0)
                second = await adapter.poll_once()
                self.assertEqual(second["values"]["humidity"], 66.0)
                self.assertIsNotNone(adapter._proc)
                self.assertNotEqual(adapter._proc.pid, original.pid)
            finally:
                await adapter.aclose()
            self.assertEqual(
                sum(line.startswith("started:")
                    for line in log.read_text().splitlines()), 2,
            )

    async def test_timeout_kills_and_reaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter, _ = self.new_adapter(tmp, "hang", timeout=0.2)
            with self.assertRaises(SDKSnapshotError) as caught:
                await asyncio.wait_for(adapter.poll_once(), 4)
            self.assertEqual(caught.exception.code, "SDK_TIMEOUT")
            self.assertIsNone(adapter._proc)
            await adapter.aclose()

    async def test_cancellation_kills_and_releases_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter, log = self.new_adapter(tmp, "hang", timeout=10)
            task = asyncio.create_task(adapter.poll_once())
            for _ in range(300):
                if log.exists() and "poll:" in log.read_text():
                    break
                await asyncio.sleep(.01)
            self.assertIn("poll:", log.read_text())
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, 4)
            self.assertIsNone(adapter._proc)
            async with asyncio.timeout(1):
                await adapter.aclose()

    async def test_oversized_frame_is_rejected_and_cleaned(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter, _ = self.new_adapter(tmp, "oversize")
            with self.assertRaises(SDKSnapshotError) as caught:
                await adapter.poll_once()
            self.assertEqual(caught.exception.code, "SDK_PROCESS_FAILURE")
            self.assertIsNone(adapter._proc)

    async def test_wrong_device_never_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter, _ = self.new_adapter(tmp, "wrong-device")
            with self.assertRaises(SDKSnapshotError):
                await adapter.poll_once()
            self.assertIsNone(adapter._proc)

    async def test_startup_failure_is_sanitized_and_reaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter, _ = self.new_adapter(tmp, "startup-error")
            with self.assertRaises(SDKSnapshotError) as caught:
                await adapter.poll_once()
            self.assertEqual(caught.exception.code, "SDK_SESSION_FAILED")
            self.assertIsNone(adapter._proc)

    async def test_aclose_idempotent_then_explicit_new_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter, log = self.new_adapter(tmp, "ok")
            await adapter.poll_once()
            await adapter.aclose()
            await adapter.aclose()
            self.assertIsNone(adapter._proc)
            await adapter.poll_once()
            await adapter.aclose()
            self.assertEqual(sum(x.startswith("started:") for x in log.read_text().splitlines()), 2)


class FakeFunction:
    def __init__(self, fn):
        self.fn = fn
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        return self.fn(*args)


class FakeSDK:
    def __init__(self):
        self.events = []
        self.buffers = []
        self.results = iter((0, 26, 0))
        for name, fn in {
            "nabtoStartup": lambda _: self.call("startup"),
            "nabtoInstallDefaultStaticResources": lambda _: self.call("resources"),
            "nabtoOpenSession": self.open,
            "nabtoRpcSetDefaultInterface": self.interface,
            "nabtoRpcInvoke": self.invoke,
            "nabtoCloseSession": lambda _: self.call("close"),
            "nabtoShutdown": lambda: self.call("shutdown"),
            "nabtoFree": lambda _: None,
        }.items():
            setattr(self, name, FakeFunction(fn))

    def call(self, name):
        self.events.append(name)
        return 0

    def open(self, pointer, identity, password):
        self.events.append("open")
        ct.cast(pointer, ct.POINTER(ct.c_void_p))[0] = ct.c_void_p(42)
        return 0

    def interface(self, session, xml, pointer):
        self.events.append("interface")
        return 0

    def invoke(self, session, url, pointer):
        self.events.append("invoke")
        status = next(self.results)
        if status == 0:
            body = json.dumps({
                "response": {"values": [
                    {"value": n} for n in (370, 340, 350, 380, 65)
                ]}
            }).encode()
            buffer = ct.create_string_buffer(body)
            self.buffers.append(buffer)
            ct.cast(pointer, ct.POINTER(ct.c_void_p))[0] = ct.cast(buffer, ct.c_void_p)
        return status


class PersistentWorkerProtocolTests(unittest.TestCase):
    def test_native_sdk_lifecycle_one_session_and_in_session_recovery(self):
        path = ROOT / "persistent_rpc45_worker.py"
        spec = importlib.util.spec_from_file_location("persistent_rpc45_worker", path)
        worker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(worker)
        fake = FakeSDK()
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp)
            (profile / "client.crt").write_text("fixture")
            (profile / "client-encrypted.key").write_text("fixture")
            config = json.dumps({
                "identity": "test@example.invalid",
                "host": DEVICE + ".remote.lscontrol.dk",
                "passphrase": "fixture-secret",
            })
            stdin = io.TextIOWrapper(io.BytesIO(
                (config + "\nPOLL\nPOLL\nPOLL\nCLOSE\n").encode()
            ))
            stdout = io.StringIO()
            with patch.object(worker.ct, "CDLL", return_value=fake), \
                 patch.object(sys, "stdin", stdin), \
                 patch.object(sys, "stdout", stdout), \
                 patch.object(sys, "argv", ["worker.py", "--serve-stdio"]), \
                 patch.dict(os.environ, {"GENVEX_NABTO_PROFILE": tmp}):
                self.assertEqual(worker.main(), 0)
            lines = stdout.getvalue().splitlines()
            self.assertEqual(len(lines), 4)
            self.assertEqual(lines[0], 'GENVEX_PERSISTENT_READY={"ok":true}')
            frames = [json.loads(line.split("=", 1)[1]) for line in lines[1:]]
            self.assertEqual([f["ok"] for f in frames], [True, False, True])
            self.assertEqual(frames[1]["status"], 26)
            self.assertEqual(frames[0]["snapshot"]["values"]["supply_air"], 7.0)
            self.assertEqual(frames[2]["snapshot"]["values"]["humidity"], 65.0)
            self.assertEqual(fake.events, [
                "startup", "resources", "open", "interface",
                "invoke", "invoke", "invoke", "close", "shutdown",
            ])
            self.assertNotIn("fixture-secret", stdout.getvalue())

    def test_persistent_mode_requires_explicit_opt_in(self):
        source = (ROOT / "polling_runtime.py").read_text()
        self.assertIn('if config.get("persistent_session", False):', source)
        self.assertIn('else:\n        adapter = SDKSnapshotAdapter(', source)
        self.assertIn('await adapter.aclose()', source)
        compile((ROOT / "persistent_rpc45_worker.py").read_bytes(),
                "<persistent_rpc45_worker>", "exec")


if __name__ == "__main__":
    unittest.main()
