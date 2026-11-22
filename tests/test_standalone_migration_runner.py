"""Regression: Steam Deck migration runner must surface publication failures.

Fully isolated: fake Git/curl/migrator; no GitHub auth, network or HAOS.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_standalone_migration_from_deck.sh"
PINNED = "a" * 40


class StandaloneMigrationRunnerTests(unittest.TestCase):
    def run_case(self, publish_rc: int) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "bin").mkdir()
            (directory / "genvex-remote-standalone" / ".git").mkdir(parents=True)

            git = directory / "bin/git"
            git.write_text(
                '#!/bin/sh\n'
                'if [ "$1" = "filter-repo" ] && [ "$2" = "--version" ]; then\n'
                '  echo "git-filter-repo"\n'
                '  exit 0\n'
                'fi\n'
                'if [ "$1" = "-C" ] && [ "$3" = "remote" ]; then\n'
                '  exit 1\n'
                'fi\n'
                'echo "Unexpected fake Git command" >&2\n'
                'exit 99\n',
                encoding="utf-8",
            )
            git.chmod(0o755)

            curl = directory / "bin/curl"
            curl.write_text(
                '#!/bin/sh\n'
                'while [ "$#" -gt 0 ]; do\n'
                '  if [ "$1" = "-o" ]; then shift; dest="$1"; fi\n'
                '  shift\n'
                'done\n'
                'test -n "$dest" || exit 18\n'
                "cat > \"$dest\" <<'MIGRATOR'\n"
                '#!/bin/bash\n'
                'case "$1" in\n'
                '  --verify) echo "STANDALONE_VERIFY: PASS"; exit 0 ;;\n'
                f'  --publish) echo "SIMULATED_PUBLISH_RC={publish_rc}"; exit {publish_rc} ;;\n'
                '  *) echo "Unexpected fake migrator mode" >&2; exit 19 ;;\n'
                'esac\n'
                'MIGRATOR\n',
                encoding="utf-8",
            )
            curl.chmod(0o755)

            env = os.environ.copy()
            env["HOME"] = str(directory)
            env["PATH"] = str(directory / "bin") + os.pathsep + env["PATH"]
            env.pop("GENVEX_STANDALONE_DIR", None)
            proc = subprocess.run(
                ["bash", str(RUNNER), PINNED],
                cwd=directory,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=20,
                check=False,
            )
            return proc.returncode, proc.stdout

    def test_publish_failure_is_not_misreported_as_success(self) -> None:
        rc, output = self.run_case(37)
        self.assertEqual(rc, 37, output)
        self.assertIn("SIMULATED_PUBLISH_RC=37", output)
        self.assertIn("STEAM_DECK_EXIT_CODE: 37", output)
        self.assertNotIn("MIGRATION_OPERATOR_GATE: PASS", output)

    def test_successful_publish_reports_pass(self) -> None:
        rc, output = self.run_case(0)
        self.assertEqual(rc, 0, output)
        self.assertIn("MIGRATION_OPERATOR_GATE: PASS", output)
        self.assertIn("STEAM_DECK_EXIT_CODE: 0", output)


if __name__ == "__main__":
    unittest.main()
