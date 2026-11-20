"""Offline tests: fake-only App mode never impersonates live sensor snapshots."""
from __future__ import annotations

from http.client import HTTPConnection
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1] / "runtime"
sys.path.insert(0, str(HERE))
from diagnostic_http_server import DiagnosticHTTPServer

spec = importlib.util.spec_from_file_location("diag_app_bootstrap", HERE / "app_bootstrap.py")
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class DiagnosticSocketTests(unittest.TestCase):
    def setUp(self):
        self.server = DiagnosticHTTPServer(bind_host="127.0.0.1", port=0)
        self.server.start()
        self.addCleanup(self.server.stop)

    def request(self, path, method="GET", headers=None):
        client = HTTPConnection("127.0.0.1", self.server.port, timeout=3)
        try:
            client.request(method, path, headers=headers or {})
            response = client.getresponse()
            return response.status, dict(response.getheaders()), response.read(4097)
        finally:
            client.close()

    def test_explicitly_synthetic_data_at_separate_path(self):
        status, headers, body = self.request("/v1/diagnostic")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        doc = json.loads(body)
        self.assertEqual(doc["mode"], "DIAGNOSTIC_ONLY")
        self.assertIs(doc["synthetic"], True)
        self.assertEqual(doc["notice"], "NOT_REAL_SENSOR_DATA")
        self.assertEqual(doc["values"]["humidity"], 50.0)
        for forbidden in ("device_id", "timestamp_utc", "schema_version", "health"):
            self.assertNotIn(forbidden, doc)

    def test_live_endpoint_cannot_return_diagnostic_values(self):
        # Even production-looking authorization must not enable this path.
        for path in ("/v1/snapshot", "/v1/snapshot?x=1", "/unknown", "/v1/diagnostic?x=1"):
            with self.subTest(path=path):
                status, _, data = self.request(path, headers={"Authorization": "Bearer " + "X" * 43})
                self.assertEqual(status, 404)
                self.assertEqual(json.loads(data), {"error": "not_found"})
        status, _, _ = self.request("/v1/diagnostic", method="DELETE")
        self.assertEqual(status, 404)
        status, _, _ = self.request("/v1/diagnostic", headers={"Content-Length": "0"})
        self.assertEqual(status, 400)

    def test_unrecognized_bindings_rejected(self):
        for host, port in (("192.0.2.3", 18275), ("0.0.0.0", 0), ("0.0.0.0", 18111)):
            with self.subTest(host=host, port=port):
                with self.assertRaises(ValueError):
                    DiagnosticHTTPServer(bind_host=host, port=port)


class DiagnosticBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.options = self.root / "options.json"
        self.profile = self.root / "profile"
        self.token_file = self.root / "ipc-token"
        self.settings = {
            "diagnostic_only": True,
            "device_id": "", "identity": "", "unlock_secret": "",
            "ipc_token": "", "poll_seconds": 60,
        }
        self.write_options()

    def write_options(self):
        self.options.write_text(json.dumps(self.settings))

    def test_requires_explicit_boolean_opt_in(self):
        self.assertIs(bootstrap.read_options(self.options)["diagnostic_only"], True)
        for val in ("true", 1, None, []):
            self.settings["diagnostic_only"] = val
            self.write_options()
            with self.subTest(value=val), self.assertRaises(ValueError):
                bootstrap.read_options(self.options)

    def test_rejects_any_live_credential_or_device_id(self):
        for field in ("device_id", "identity", "unlock_secret", "ipc_token"):
            self.settings[field] = "PRIVATE_DO_NOT_USE"
            self.write_options()
            with self.subTest(field=field), self.assertRaises(ValueError):
                bootstrap.read_options(self.options)
            self.settings[field] = ""
        self.settings["bad_extra"] = True
        self.write_options()
        with self.assertRaises(ValueError):
            bootstrap.read_options(self.options)

    def test_diagnostic_main_never_touches_profile_or_sdk(self):
        with (
            patch.object(bootstrap, "OPTIONS", self.options),
            patch.object(bootstrap, "PROFILE", self.profile),
            patch.object(bootstrap, "TOKEN", self.token_file),
            patch.object(bootstrap, "run_diagnostic_only") as diagnostics,
            patch.object(bootstrap, "validate_private_profile") as validation,
            patch.object(bootstrap, "write_token") as write_token,
        ):
            bootstrap.main()
        diagnostics.assert_called_once_with()
        validation.assert_not_called()
        write_token.assert_not_called()
        self.assertFalse(self.profile.exists())
        self.assertFalse(self.token_file.exists())

    def test_existing_profile_or_token_fail_closed(self):
        for existing in (self.profile, self.token_file):
            existing.touch()
            with (
                patch.object(bootstrap, "OPTIONS", self.options),
                patch.object(bootstrap, "PROFILE", self.profile),
                patch.object(bootstrap, "TOKEN", self.token_file),
                patch.object(bootstrap, "run_diagnostic_only") as diagnostics,
            ):
                with self.subTest(existing=existing.name), self.assertRaises(SystemExit):
                    bootstrap.main()
                diagnostics.assert_not_called()
            existing.unlink()
        self.profile.symlink_to(self.root / "nonexistent-target")
        with (
            patch.object(bootstrap, "OPTIONS", self.options),
            patch.object(bootstrap, "PROFILE", self.profile),
            patch.object(bootstrap, "TOKEN", self.token_file),
            patch.object(bootstrap, "run_diagnostic_only") as diagnostics,
        ):
            with self.assertRaises(SystemExit):
                bootstrap.main()
            diagnostics.assert_not_called()


if __name__ == "__main__":
    unittest.main()
