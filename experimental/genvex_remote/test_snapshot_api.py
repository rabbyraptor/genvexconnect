"""No sockets or cloud access: internal snapshot endpoint contract tests."""
from datetime import datetime, timedelta, timezone
import json
import unittest

from ipc_auth import new_ipc_token
from snapshot_api import handle_read_request


class SnapshotApiTests(unittest.TestCase):
    def setUp(self):
        self.device = "123456789012"
        self.token = new_ipc_token()
        self.snapshot = {
            "schema_version": 1,
            "device_id": self.device,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "health": "ok",
            "values": {"supply_air": 6.7, "outdoor_air": -0.1, "exhaust_air": 1.5,
                       "extract_air": 7.7, "humidity": 65},
        }

    def call(self, **overrides):
        args = dict(
            method="GET", path="/v1/snapshot",
            authorization="Bearer " + self.token, expected_token=self.token,
            device_id=self.device, snapshot=self.snapshot,
        )
        args.update(overrides)
        return handle_read_request(**args)

    def test_authorized_fresh_snapshot(self):
        code, body = self.call()
        self.assertEqual(code, 200)
        parsed = json.loads(body)
        self.assertEqual(parsed["values"]["humidity"], 65.0)
        self.assertEqual(set(parsed), {"schema_version", "device_id",
                                      "timestamp_utc", "health", "values"})

    def test_missing_token(self):
        code, _ = self.call(authorization=None)
        self.assertEqual(code, 401)

    def test_wrong_token(self):
        code, _ = self.call(authorization="Bearer " + new_ipc_token())
        self.assertEqual(code, 401)

    def test_wrong_route(self):
        for method, path in (("POST", "/v1/snapshot"), ("GET", "/v1/enroll"),
                             ("GET", "/debug"), ("GET", "/v1/snapshot?secret=yes")):
            with self.subTest(method=method, path=path):
                code, _ = self.call(method=method, path=path)
                self.assertEqual(code, 404)

    def test_authentication_precedes_route(self):
        code, _ = self.call(path="/debug", authorization=None)
        self.assertEqual(code, 401)

    def test_missing_or_wrong_device_data_unavailable(self):
        self.snapshot["device_id"] = "000000000000"
        code, body = self.call()
        self.assertEqual(code, 503)
        self.assertNotIn(b"000000000000", body)

    def test_stale_unavailable(self):
        self.snapshot["timestamp_utc"] = (
            datetime.now(timezone.utc) - timedelta(minutes=4)
        ).isoformat()
        code, _ = self.call()
        self.assertEqual(code, 503)

    def test_does_not_leak_unknown_fields(self):
        self.snapshot["secret"] = "SECRET_DO_NOT_EXPOSE"
        code, body = self.call()
        self.assertEqual(code, 503)
        self.assertNotIn(b"SECRET", body)


if __name__ == "__main__":
    unittest.main()
