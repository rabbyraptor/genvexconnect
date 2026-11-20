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


    def test_core_dns_audit_is_read_only(self):
        script = ROOT / "scripts/audit_haos_core_app_dns_readonly.sh"
        result = subprocess.run(["sh", "-n", str(script)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        contents = script.read_text()
        self.assertIn("socket.getaddrinfo", contents)
        self.assertIn("docker exec homeassistant python3", contents)
        self.assertNotRegex(
            contents,
            r"\\bdocker\\s+(?:run|start|stop|rm|load|build|create|cp|pull|push)\\b"
        )
        self.assertNotIn("socket.create_connection", contents)
        self.assertNotIn("urllib.request", contents)


    def test_future_core_to_app_diagnostic_acceptance_is_read_only(self):
        script = ROOT / "scripts/verify_haos_remote_diagnostic_readonly.sh"
        result = subprocess.run(["sh", "-n", str(script)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        contents = script.read_text()
        self.assertIn("local-genvex-nabto-remote", contents)
        self.assertIn("app_local_genvex_nabto_remote", contents)
        self.assertIn("docker exec -i homeassistant python3 -B -", contents)
        self.assertIn('check("/v1/diagnostic", 200)', contents)
        self.assertIn('check("/v1/snapshot", 404)', contents)
        self.assertIn("NOT_REAL_SENSOR_DATA", contents)
        self.assertIn('"synthetic"', contents)
        self.assertNotRegex(
            contents,
            r"\\bdocker\\s+(?:run|start|stop|rm|load|build|create|cp|pull|push|network\\s+create)\\b"
        )
        self.assertNotIn("Bearer ", contents)
        self.assertNotIn("urllib.request", contents)



if __name__ == "__main__":
    unittest.main()
