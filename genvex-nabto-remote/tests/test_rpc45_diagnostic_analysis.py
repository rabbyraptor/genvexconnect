"""Offline metadata analyzer regression tests (synthetic log data only)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import io
from contextlib import redirect_stdout
from pathlib import Path
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2] / "scripts" / "analyze_rpc45_metadata.py"
spec = importlib.util.spec_from_file_location("dev6_rpc45_analyzer", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def cycle(time: datetime, success: bool, before="451", after="451") -> str:
    stamp = time.isoformat()
    status = "OK" if success else "FEJL"
    return (f"2026/11/22 14:00:00 RPC45 {stamp} {status} 5.03s "
            f"PID_BEFORE={before} PID_AFTER={after}")


class RPC45AnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 11, 22, 13, 54, 56, tzinfo=timezone.utc)

    def test_intervals_and_worker_recovery(self):
        lines = []
        for offset in (0, 374, 748, 1123):
            lines.extend((
                cycle(self.start + timedelta(seconds=offset), False),
                cycle(self.start + timedelta(seconds=offset + 60), True),
            ))
        result = module.analyze_lines(lines)
        self.assertEqual(result["cycles"], 8)
        self.assertEqual(result["failures"], 4)
        self.assertEqual(result["successes"], 4)
        self.assertEqual(result["failure_intervals_seconds"], [374.0, 374.0, 375.0])
        self.assertEqual(result["recovered_next_cycle"], 4)
        self.assertEqual(result["worker_reused_on_recovery"], 4)

    def test_changed_worker_does_not_count_as_reused(self):
        lines = [
            cycle(self.start, False, before="11", after="11"),
            cycle(self.start + timedelta(seconds=60), True, before="22", after="22"),
        ]
        result = module.analyze_lines(lines)
        self.assertEqual(result["recovered_next_cycle"], 1)
        self.assertEqual(result["worker_reused_on_recovery"], 0)

    def test_unknown_sensitive_lines_ignored_not_reflected(self):
        secret = "FAKE_NEVER_FORWARD_THIS_SECRET"
        lines = [
            "RPC45_DIAGNOSTIC rpc_status=26 elapsed_ms=5000",
            secret,
            cycle(self.start, False),
            cycle(self.start + timedelta(seconds=60), True),
        ]
        result = module.analyze_lines(lines)
        self.assertEqual(result["ignored_lines"], 2)
        self.assertNotIn(secret, repr(result))
        self.assertEqual(result["cycles"], 2)

    def test_rejects_oversize_input_and_out_of_order_timestamp(self):
        lines = [
            "X" * 4000,
            cycle(self.start, True),
            cycle(self.start - timedelta(seconds=1), False),
        ]
        result = module.analyze_lines(lines)
        self.assertEqual(result["cycles"], 1)
        self.assertEqual(result["ignored_lines"], 2)

    def test_line_limit_fails_closed(self):
        with self.assertRaises(ValueError):
            module.analyze_lines(iter(["private"] * 10001))

    def test_command_outputs_only_summary(self):
        lines = [cycle(self.start, False), cycle(self.start + timedelta(seconds=60), True)]
        output = io.StringIO()
        with patch("sys.stdin", io.StringIO("\n".join(lines))), redirect_stdout(output):
            self.assertEqual(module.main(), 0)
        self.assertIn('"failures":1', output.getvalue())
        self.assertNotIn("PID_BEFORE", output.getvalue())
        self.assertNotIn("2026-11-22T13:54", output.getvalue())


if __name__ == "__main__":
    unittest.main()
