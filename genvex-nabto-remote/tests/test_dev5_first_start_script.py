"""Offline static validation of the DEV5 first-start operator launcher.

No remote connection or real App start is exercised by these tests.
"""
from __future__ import annotations

import ast
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/run_dev5_first_start_from_deck.sh"


class DEV5FirstStartScriptTests(unittest.TestCase):
    def test_shell_and_embedded_python_parse(self):
        result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        source = SCRIPT.read_text()
        blocks = re.findall(r"^python3 - <<'PY'\n(.*?)^PY$", source,
                            flags=re.MULTILINE | re.DOTALL)
        # Python inside docker exec starts as "python3 - <<'PY'" too.
        docker_blocks = re.findall(r"^docker exec -i .*? python3 - <<'PY'\n(.*?)^PY$",
                                   source, flags=re.MULTILINE | re.DOTALL)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(len(docker_blocks), 1)
        for code in blocks + docker_blocks:
            ast.parse(code)

    def test_one_explicit_start_no_other_mutations(self):
        source = SCRIPT.read_text()
        self.assertEqual(source.count("ha apps start local_genvex_nabto_remote"), 1)
        for banned in (
            "ha apps stop", "ha apps update", "ha apps restart",
            "docker restart", "docker cp", "ha backups new",
            "docker run", "options.json\",",
        ):
            self.assertNotIn(banned, source)

    def test_live_checks_and_secret_redaction_contract(self):
        source = SCRIPT.read_text()
        for expected in (
            "DEV5_PRESTART: PASS",
            "SUPERVISOR_DEV5_STARTED: PASS",
            "DEV5_DIAGNOSTIC_IMAGE_PARITY: PASS",
            "IPC_V1_VALUES:",
            "PERSISTENT_WORKER_COUNT:",
            "HA_REGISTERED_ENTITIES:",
            "DEV5_LIVE_RESULT: PASS",
            "STEAM_DECK_EXIT_CODE:",
            "printf '\\033[3J\\033[2J\\033[H'",
        ):
            self.assertIn(expected, source)
        self.assertNotIn("print(token)", source)
        self.assertNotIn("print(config)", source)
        self.assertNotIn("print(snapshot)", source)


if __name__ == "__main__":
    unittest.main()
