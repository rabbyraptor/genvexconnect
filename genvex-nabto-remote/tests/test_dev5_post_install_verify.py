"""DEV5 post-install verification tests: fake backup + pinned source only."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/dev5_post_install_verify.py"
spec = importlib.util.spec_from_file_location("dev5_post_install_verify", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class DEV5PostInstallTests(unittest.TestCase):
    def test_expected_hashes_match_real_packaged_dev5_sources(self):
        source = ROOT / "genvex-nabto-remote"
        self.assertEqual(len(gate.EXPECTED), 20)
        self.assertEqual(gate.inspect_source(source, gate.EXPECTED, True), 20)

    def test_detect_one_changed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "config.yaml").write_text("bad")
            with self.assertRaises(gate.GateBlocked):
                gate.inspect_source(path, {"config.yaml": "0" * 40}, True)

    def test_finds_new_backup_with_dev4_app(self):
        rows = [
            {"slug": "before_old1", "date": "2026-11-20T21:00:00+00:00"},
            {"slug": "after_new1", "date": "2026-11-22T11:30:00+00:00"},
        ]
        def detail(slug):
            self.assertEqual(slug, "after_new1")
            return {"type": "partial", "apps": [
                {"slug": gate.APP, "version": "0.1.0-dev4"}
            ]}
        self.assertEqual(
            gate.find_new_backup(rows, detail),
            ("after_new1", "2026-11-22T11:30:00+00:00"),
        )

    def test_absent_app_or_wrong_version_rejected(self):
        rows = [{"slug": "after_new1", "date": "2026-11-22T11:30:00Z"}]
        for info in (
            {"type": "partial", "apps": []},
            {"type": "partial", "apps": [{"slug": gate.APP, "version": "0.1.0-dev5"}]},
            {"type": "unknown", "apps": [gate.APP]},
        ):
            self.assertIsNone(gate.find_new_backup(rows, lambda _: info))

    def test_runner_readonly_and_syntax(self):
        runner = ROOT / "scripts/run_dev5_post_install_from_deck.sh"
        result = subprocess.run(["bash", "-n", str(runner)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        source = runner.read_text()
        self.assertIn("python3 - --execute-readonly", source)
        self.assertIn("STEAM_DECK_EXIT_CODE:", source)
        self.assertIn("printf '\\033[3J\\033[2J\\033[H'", source)
        for forbidden in ("ha apps start", "ha apps update", "ha apps stop",
                          "ha apps restart", "docker restart"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
