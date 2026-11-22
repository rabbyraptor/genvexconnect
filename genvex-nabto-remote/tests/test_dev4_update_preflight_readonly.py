"""Static safety contract for the read-only DEV4 versioned-update preflight."""
from __future__ import annotations

from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/preflight_haos_dev4_versioned_upgrade_readonly.sh"


class DEV4UpdatePreflightTests(unittest.TestCase):
    def test_script_syntax_and_readonly_contract(self):
        proc = subprocess.run(["bash", "-n", str(SOURCE)], capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        source = SOURCE.read_text()
        for expected in (
            '"ha", "apps", "info"',
            '"docker", "inspect"',
            '"ha", "backups", "list"',
            '"0.1.0-dev4"',
            "VERSIONED_UPDATE_PREFLIGHT:",
            "HOST_PUBLISHED_PORT:",
            "FUTURE_STAGE_OCCUPIED:",
            "printf '\\033[3J\\033[2J\\033[H'",
        ):
            self.assertIn(expected, source)
        for forbidden in (
            "ha apps update",
            "ha apps stop",
            "ha apps restart",
            "docker restart",
            "docker exec",
            "docker cp",
            "ha backups new",
            "shutil.copy",
            "os.replace(",
            "subprocess.Popen(",
            "/data/options.json",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
