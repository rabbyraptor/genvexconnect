"""Offline Nabto status-26 JSON event redaction tests (no SDK or secrets)."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

WORKER = (
    Path(__file__).resolve().parents[1] / "runtime/persistent_rpc45_worker.py"
)
spec = importlib.util.spec_from_file_location("dev4_worker_diagnostic", WORKER)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class WorkerEventTests(unittest.TestCase):
    def test_numeric_event_extracts_only_allowed_integer(self):
        raw = json.dumps({"error": {
            "body": "SENSITIVE_BODY", "detail": "SENSITIVE_DETAIL",
            "header": "SENSITIVE_HEADER", "event": 1000015,
        }})
        self.assertEqual(worker.numeric_error_event(raw), 1000015)
        self.assertIsNone(worker.numeric_error_event('{"error":{"event":true}}'))
        self.assertIsNone(worker.numeric_error_event('{"error":{"event":"1000015"}}'))
        self.assertIsNone(worker.numeric_error_event("not json"))
        self.assertIsNone(worker.numeric_error_event(raw * 2000))

    def test_event_file_contains_no_raw_sdk_strings(self):
        with tempfile.TemporaryDirectory() as directory:
            record_path = Path(directory) / "event.log"
            actual_open = os.open

            def safe_open(path, flags, mode=0o777, **kwargs):
                if path == "/data/rpc45_json_diagnostic.log":
                    path = str(record_path)
                return actual_open(path, flags, mode, **kwargs)

            raw = json.dumps({"error": {
                "event": 1000015,
                "body": "NEVER_LOG_SENSITIVE_BODY",
                "header": "NEVER_LOG_SENSITIVE_HEADER",
                "detail": "NEVER_LOG_SENSITIVE_DETAIL",
            }})
            with patch.object(worker.os, "open", side_effect=safe_open):
                worker.record_error_event(26, raw)
                worker.record_error_event(0, raw)

            lines = record_path.read_text().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["event"], 1000015)
            for secret in ("SENSITIVE_BODY", "SENSITIVE_HEADER", "SENSITIVE_DETAIL"):
                self.assertNotIn(secret, lines[0])


if __name__ == "__main__":
    unittest.main()
