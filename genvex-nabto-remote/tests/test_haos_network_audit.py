"""Static and fake-Docker tests for the read-only HAOS audit script."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/audit_haos_remote_network_readonly.sh"


class ReadOnlyAuditTests(unittest.TestCase):
    def test_shell_syntax(self):
        result = subprocess.run(["sh", "-n", str(SCRIPT)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_no_docker_mutating_verbs(self):
        script = SCRIPT.read_text()
        # Check literal docker invocations (not comments or output strings).
        commands = re.findall(r"^\s*docker\s+(\w+)", script, re.MULTILINE)
        self.assertTrue(commands)
        self.assertEqual(set(commands), {"version", "info", "inspect", "network", "image"})
        self.assertNotRegex(script, r"\bdocker\s+(?:run|start|stop|rm|exec|cp|load|build|create|pull|push|system|container\s+update)\b")

    def test_fake_docker_only_receives_inspection_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            shim = temp / "docker"
            log = temp / "calls"
            shim.write_text(
                "#!/bin/sh\n"
                'printf "%s\\n" "$1" >> "$AUDIT_TEST_CALLS"\n'
                'case "$1" in\n'
                "  version|info|inspect) exit 0 ;;\n"
                '  network) test "$2" = inspect ;;\n'
                '  image) test "$2" = inspect ;;\n'
                "  *) exit 88 ;;\n"
                "esac\n"
            )
            shim.chmod(0o700)
            env = os.environ.copy()
            env["PATH"] = str(temp) + os.pathsep + env.get("PATH", "")
            env["AUDIT_TEST_CALLS"] = str(log)
            result = subprocess.run(
                ["sh", str(SCRIPT)], env=env,
                capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("AUDIT COMPLETE: READ-ONLY", result.stdout)
            calls = log.read_text().splitlines()
            self.assertTrue(calls)
            self.assertLessEqual(set(calls), {"version", "info", "inspect", "network", "image"})


if __name__ == "__main__":
    unittest.main()
