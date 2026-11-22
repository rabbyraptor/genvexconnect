"""DEV8.4.1 complete fake-worker -> adapter -> state -> HTTP integration gate.

Only Python's own child process and loopback HTTP are used. No Nabto SDK,
credentials, HAOS tunnel, gateway, or vendor endpoints are accessed.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

RUNTIME = Path(__file__).resolve().parents[1] / "runtime"
sys.path.insert(0, str(RUNTIME))

from persistent_sdk_adapter import PersistentSDKSnapshotAdapter
from polling_http_server import SnapshotHTTPServer
from raw_snapshot_state_v3 import RawV3SnapshotState

DEVICE = "123456789012"
TOKEN = "X" * 43
BASE_VALUES = {
    "supply_air": 6.8, "outdoor_air": 0.8,
    "exhaust_air": 2.2, "extract_air": 7.8, "humidity": 67.0,
}
RAW_BASE = {
    "supply_air": 368, "outdoor_air": 308,
    "exhaust_air": 322, "extract_air": 378, "humidity": 67,
}
RAW_EXTRA = {
    "frost_protection_temp": 0, "fan_duty_supply": 6000,
    "fan_duty_extract": 5800, "fan_rpm_supply": 2432,
    "fan_rpm_extract": 2268, "preheat_pwm": 0,
    "reheat_pwm": 0, "bypass_active_raw": 0,
    "bypass_analog_raw": 0, "alarm_word_1_raw": 0,
    "alarm_word_2_raw": 0, "rotor_rpm": 10,
}

CHILD = r"""
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

mode, audit_path = sys.argv[1:3]
credentials = json.loads(sys.stdin.buffer.readline())
assert set(credentials) == {"identity", "host", "passphrase"}
assert credentials["host"] == "123456789012.remote.lscontrol.dk"
assert credentials["identity"] == "fake@example.invalid"
assert credentials["passphrase"] == "fixture-only"
audit = Path(audit_path)
with audit.open("a") as file:
    file.write("START " + str(os.getpid()) + "\n")
print('GENVEX_PERSISTENT_READY={"ok":true}', flush=True)
count = 0
while True:
    command = sys.stdin.buffer.readline()
    if command == b"CLOSE\n" or not command:
        break
    assert command in (b"POLL3\n", b"POLL\n")
    count += 1
    with audit.open("a") as file:
        file.write(command.decode().strip() + "\n")
    if mode == "hang" and count == 2:
        time.sleep(30)
        continue
    stamp = datetime.now(timezone.utc).isoformat()
    doc = {
        "schema_version": 1,
        "device_id": "123456789012",
        "timestamp_utc": stamp,
        "health": "ok",
        "values": {
            "supply_air": 6.8, "outdoor_air": 0.8,
            "exhaust_air": 2.2, "extract_air": 7.8, "humidity": 67.0,
        },
    }
    if command == b"POLL3\n":
        doc["schema_version"] = 3
        doc["raw_values"] = {
            "supply_air": 368, "outdoor_air": 308,
            "exhaust_air": 322, "extract_air": 378, "humidity": 67,
        }
        full = {
            "frost_protection_temp": 0, "fan_duty_supply": 6000,
            "fan_duty_extract": 5800, "fan_rpm_supply": 2432,
            "fan_rpm_extract": 2268, "preheat_pwm": 0,
            "reheat_pwm": 0, "bypass_active_raw": 0,
            "bypass_analog_raw": 0, "alarm_word_1_raw": 0,
            "alarm_word_2_raw": 0, "rotor_rpm": 10,
        }
        # The second poll models one failed optional twelve-register RPC45.
        doc["optional"] = {"raw_registers": {} if count == 2 else full}
    print("GENVEX_PERSISTENT_RESULT="
          + json.dumps({"ok": True, "snapshot": doc},
                       separators=(",", ":")), flush=True)
with audit.open("a") as file:
    file.write("CLOSED\n")
"""


def http_request(port: int, path: str, *, token: str | None = TOKEN,
                 method: str = "GET") -> tuple[int, dict]:
    headers = {"Accept": "application/json"}
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    request = Request(
        f"http://127.0.0.1:{port}{path}", headers=headers, method=method,
    )
    try:
        with urlopen(request, timeout=3) as response:
            return response.status, json.loads(response.read(4097))
    except HTTPError as response:
        return response.code, json.loads(response.read(4097))


class CombinedTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        (self.folder / "worker.py").write_text("# fake worker fixture\n")
        self.audit_path = self.folder / "audit.log"
        self.adapter = PersistentSDKSnapshotAdapter(
            device_id=DEVICE,
            identity="fake@example.invalid",
            unlock_secret="fixture-only",
            profile_dir=str(self.folder),
            worker_file=str(self.folder / "worker.py"),
            raw_registers_v3=True,
            startup_timeout_seconds=3,
            timeout_seconds=1.2,
            command=(
                sys.executable, "-u", "-c", CHILD,
                "normal", str(self.audit_path),
            ),
        )
        self.state = RawV3SnapshotState(self.adapter)
        self.server = SnapshotHTTPServer(
            bind_host="127.0.0.1",
            port=0, token=TOKEN, device_id=DEVICE,
            snapshot_provider=self.state.current,
            v3_snapshot_provider=self.state.current_v3,
        )
        self.server.start()
        self.port = self.server._server.server_port

    async def asyncTearDown(self):
        await self.adapter.aclose()
        await asyncio.to_thread(self.server.stop)

    async def request(self, path: str, *, token: str | None = TOKEN,
                      method: str = "GET"):
        return await asyncio.to_thread(
            http_request, self.port, path, token=token, method=method,
        )

    async def test_one_persistent_process_serves_both_contracts_without_http_polls(self):
        self.assertEqual((await self.request("/v3/snapshot"))[0], 503)
        self.assertFalse(self.audit_path.exists())

        self.assertTrue(await self.state.refresh())
        pid = self.adapter._proc.pid
        status1, v1 = await self.request("/v1/snapshot")
        status3, v3 = await self.request("/v3/snapshot")
        self.assertEqual((status1, status3), (200, 200))
        self.assertEqual(v1["schema_version"], 1)
        self.assertEqual(set(v1["values"]), set(BASE_VALUES))
        self.assertEqual(v1["values"], BASE_VALUES)
        self.assertNotIn("raw_values", v1)
        self.assertEqual(v3["schema_version"], 3)
        self.assertEqual(v3["raw_values"], RAW_BASE)
        self.assertEqual(v3["optional"]["raw_registers"], RAW_EXTRA)
        self.assertEqual(v1["timestamp_utc"], v3["timestamp_utc"])
        self.assertEqual(self.audit_path.read_text().splitlines().count("POLL3"), 1)

        for i in range(3):
            self.assertEqual((await self.request("/v3/snapshot"))[0], 200)
        self.assertEqual(self.audit_path.read_text().splitlines().count("POLL3"), 1)
        self.assertEqual((await self.request("/v3/snapshot", token=None))[0], 401)
        self.assertEqual((await self.request("/v3/snapshot", token="Y"*43))[0], 401)
        # urllib adds Content-Length: 0 for PUT, rejected by the body-free API.
        self.assertEqual((await self.request("/v3/snapshot", method="PUT"))[0], 400)
        self.assertEqual((await self.request("/v4/snapshot"))[0], 404)

        self.assertTrue(await self.state.refresh())
        self.assertEqual(self.adapter._proc.pid, pid)
        status, v3 = await self.request("/v3/snapshot")
        self.assertEqual(status, 200)
        self.assertEqual(v3["optional"]["raw_registers"], {})
        self.assertEqual((await self.request("/v1/snapshot"))[1]["values"], BASE_VALUES)

        self.assertTrue(await self.state.refresh())
        self.assertEqual(self.adapter._proc.pid, pid)
        self.assertEqual((await self.request("/v3/snapshot"))[1]["optional"]["raw_registers"], RAW_EXTRA)
        self.assertEqual(self.audit_path.read_text().splitlines().count("POLL3"), 3)

    async def test_timeout_drops_stale_v1_and_v3_and_recycles_worker(self):
        # Force the worker's second command to hang beyond the adapter timeout.
        self.adapter._command = (
            sys.executable, "-u", "-c", CHILD,
            "hang", str(self.audit_path),
        )
        self.assertTrue(await self.state.refresh())
        self.assertEqual((await self.request("/v3/snapshot"))[0], 200)
        self.assertFalse(await self.state.refresh())
        self.assertIsNone(self.adapter._proc)
        self.assertEqual((await self.request("/v1/snapshot"))[0], 503)
        self.assertEqual((await self.request("/v3/snapshot"))[0], 503)
        self.assertTrue(await self.state.refresh())
        self.assertEqual((await self.request("/v3/snapshot"))[0], 200)
        self.assertEqual(
            self.audit_path.read_text().splitlines().count("START "
                + str(self.adapter._proc.pid)), 1,
        )


if __name__ == "__main__":
    unittest.main()
