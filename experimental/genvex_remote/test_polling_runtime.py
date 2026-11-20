"""Offline tests for the candidate long-running read-only runtime HTTP bridge."""
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ipc_auth import new_ipc_token
from polling_http_server import SnapshotHTTPServer
from polling_runtime import load_config, read_token


def valid_snapshot():
    return {
        "schema_version": 1, "device_id": "123456789012",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "health": "ok",
        "values": {"supply_air": 6.7, "outdoor_air": -0.1,
                   "exhaust_air": 1.5, "extract_air": 7.7,
                   "humidity": 65.0},
    }


class RuntimeServerTests(unittest.TestCase):
    def setUp(self):
        self.token = new_ipc_token()
        self.snapshot = valid_snapshot()
        self.server = SnapshotHTTPServer(
            bind_host="127.0.0.1", port=0, token=self.token,
            device_id="123456789012",
            snapshot_provider=lambda: self.snapshot,
        )
        self.port = self.server._server.server_port
        self.server.start()
        self.addCleanup(self.server.stop)

    def request(self, *, token=None, method="GET", path="/v1/snapshot"):
        headers = {} if token is None else {"Authorization": "Bearer " + token}
        req = Request(f"http://127.0.0.1:{self.port}{path}",
                      headers=headers, method=method)
        try:
            with urlopen(req, timeout=2) as response:
                return response.status, json.loads(response.read())
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_valid_authenticated_snapshot(self):
        status, result = self.request(token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(result["values"]["humidity"], 65.0)

    def test_no_or_wrong_token_rejected(self):
        self.assertEqual(self.request()[0], 401)
        self.assertEqual(self.request(token=new_ipc_token())[0], 401)

    def test_failed_poll_unavailable_not_cached(self):
        self.assertEqual(self.request(token=self.token)[0], 200)
        self.snapshot = None
        self.assertEqual(self.request(token=self.token)[0], 503)

    def test_post_and_other_path_not_exposed(self):
        self.assertEqual(self.request(token=self.token, method="POST")[0], 404)
        self.assertEqual(self.request(token=self.token, path="/debug")[0], 404)


class RuntimeConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = {
            "device_id": "123456789012", "identity": "test",
            "unlock_secret": "fake-only", "profile_dir": str(self.root),
            "probe_file": str(self.root / "fake-probe"),
            "token_file": str(self.root / "token"),
            "bind_host": "127.0.0.1", "poll_seconds": 60,
        }
        self.path = self.root / "config.json"
        self.write()

    def write(self):
        self.path.write_text(json.dumps(self.config))
        self.path.chmod(0o600)

    def test_valid_private_config(self):
        self.assertEqual(load_config(self.path)["poll_seconds"], 60)

    def test_world_readable_config_rejected(self):
        self.path.chmod(0o644)
        with self.assertRaises(ValueError):
            load_config(self.path)

    def test_extra_field_rejected(self):
        self.config["unsafe"] = "value"
        self.write()
        with self.assertRaises(ValueError):
            load_config(self.path)

    def test_symlink_rejected(self):
        link = self.root / "link"
        link.symlink_to(self.path)
        with self.assertRaises(ValueError):
            load_config(link)

    def test_private_token_file(self):
        token = new_ipc_token()
        p = self.root / "token"
        p.write_text(token + "\n")
        p.chmod(0o600)
        self.assertEqual(read_token(p), token)
        p.chmod(0o644)
        with self.assertRaises(ValueError):
            read_token(p)


if __name__ == "__main__":
    unittest.main()
