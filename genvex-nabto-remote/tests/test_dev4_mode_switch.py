"""DEV4 opt-in polling switch tests without Home Assistant, Nabto or network."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "runtime"
sys.path.insert(0, str(ROOT))
import polling_runtime
import persistent_sdk_adapter


def config():
    return {
        "device_id": "123456789012",
        "identity": "test@example.invalid",
        "unlock_secret": "fixture-only",
        "profile_dir": "/tmp/private-fixture",
        "probe_file": "/tmp/fixture.py",
        "token_file": "/tmp/secret-test-token",
        "bind_host": "0.0.0.0",
        "poll_seconds": 60,
    }


class ConfigTests(unittest.TestCase):
    def test_old_config_remains_valid_and_implicit_oneshot(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.json"
            path.write_text(json.dumps(config()))
            path.chmod(0o600)
            self.assertFalse(polling_runtime.load_config(path).get("persistent_session", False))

    def test_explicit_true_false_and_invalid_flags(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.json"
            for enabled in (True, False):
                data = config()
                data["persistent_session"] = enabled
                path.write_text(json.dumps(data))
                path.chmod(0o600)
                self.assertEqual(polling_runtime.load_config(path)["persistent_session"], enabled)
            for value in ("true", 1, None):
                data["persistent_session"] = value
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    polling_runtime.load_config(path)

    def test_unknown_config_key_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.json"
            data = config()
            data["unrelated"] = "reject"
            path.write_text(json.dumps(data))
            path.chmod(0o600)
            with self.assertRaises(ValueError):
                polling_runtime.load_config(path)


class FakeLegacyAdapter:
    instances = []
    def __init__(self, **kwargs):
        self.device_id = kwargs["device_id"]
        self.options = kwargs
        self.__class__.instances.append(self)


class FakePersistentAdapter(FakeLegacyAdapter):
    instances = []
    close_count = 0

    async def aclose(self):
        self.__class__.close_count += 1


class FakeState:
    def __init__(self, adapter):
        self.adapter = adapter

    def current(self):
        return None


class FakePoller:
    instance = None
    def __init__(self, state, *, interval_seconds):
        self.state = state
        self.interval = interval_seconds
        self.started = False
        self.stopped = False
        FakePoller.instance = self

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True


class FakeServer:
    instance = None
    ready = None
    def __init__(self, **kwargs):
        self.options = kwargs
        self.started = False
        self.stopped = False
        FakeServer.instance = self

    def start(self):
        self.started = True
        FakeServer.ready.set()

    def stop(self):
        self.stopped = True


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        FakeLegacyAdapter.instances.clear()
        FakePersistentAdapter.instances.clear()
        FakePersistentAdapter.close_count = 0
        FakeServer.ready = asyncio.Event()

    async def launch_and_cancel(self, *, persistent):
        data = config()
        if persistent is not None:
            data["persistent_session"] = persistent
        with (
            patch.object(polling_runtime, "read_token", return_value="TEST-IPC"),
            patch.object(polling_runtime, "SDKSnapshotAdapter", FakeLegacyAdapter),
            patch.object(persistent_sdk_adapter, "PersistentSDKSnapshotAdapter", FakePersistentAdapter),
            patch.object(polling_runtime, "SnapshotState", FakeState),
            patch.object(polling_runtime, "PollingService", FakePoller),
            patch.object(polling_runtime, "SnapshotHTTPServer", FakeServer),
        ):
            task = asyncio.create_task(polling_runtime.run(data))
            try:
                await asyncio.wait_for(FakeServer.ready.wait(), 2)
            finally:
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(task, 2)
        self.assertTrue(FakeServer.instance.started)
        self.assertTrue(FakeServer.instance.stopped)
        self.assertTrue(FakePoller.instance.started)
        self.assertTrue(FakePoller.instance.stopped)

    async def test_default_legacy_mode_still_selected(self):
        await self.launch_and_cancel(persistent=None)
        self.assertEqual(len(FakeLegacyAdapter.instances), 1)
        self.assertEqual(len(FakePersistentAdapter.instances), 0)
        self.assertEqual(FakePersistentAdapter.close_count, 0)

    async def test_explicit_false_selects_legacy(self):
        await self.launch_and_cancel(persistent=False)
        self.assertEqual(len(FakeLegacyAdapter.instances), 1)
        self.assertEqual(len(FakePersistentAdapter.instances), 0)

    async def test_true_selects_persistent_and_closes_on_shutdown(self):
        await self.launch_and_cancel(persistent=True)
        self.assertEqual(len(FakeLegacyAdapter.instances), 0)
        self.assertEqual(len(FakePersistentAdapter.instances), 1)
        self.assertEqual(FakePersistentAdapter.close_count, 1)
        options = FakePersistentAdapter.instances[0].options
        self.assertEqual(options["worker_file"], str(ROOT / "persistent_rpc45_worker.py"))
        self.assertEqual(options["device_id"], "123456789012")

if __name__ == "__main__":
    unittest.main()
