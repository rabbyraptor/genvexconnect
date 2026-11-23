"""SSH-stdin regression: Supervisor CLI cannot eat the rest of streamed script."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/audit_haos_v2_ipc_supervisor_state_v2.sh"


class SupervisorAuditV2Tests(unittest.TestCase):
    def test_syntax_and_safe_preview(self):
        for shell in ("sh",):
            self.assertEqual(subprocess.run([shell, "-n", str(SCRIPT)]).returncode, 0)
            run = subprocess.run([shell, str(SCRIPT), "--preflight"],
                                 text=True, capture_output=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("PASS: inert preflight", run.stdout)

    def test_streamed_script_ha_does_not_eat_shell_input(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            # Mimic the HAOS 'ha' command that greedily reads stdin if not
            # redirected; the regression must still execute the final line.
            ha = directory / "ha"
            ha.write_text(
                "#!/bin/sh\n"
                "cat >/dev/null\n"
                "printf '%s\\n' '{\"data\":{\"installed\":true,\"state\":\"stopped\","
                "\"version\":\"0.1.0-dev1\",\"options\":{\"unlock_secret\":\"TOPSECRET\"}}}'\n",
                encoding="utf-8",
            )
            docker = directory / "docker"
            docker.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = exec ] && [ \"$2\" = -i ]; then\n"
                "  shift 3\n"
                "  exec \"$@\"\n"
                "fi\n"
                "if [ \"$1\" = inspect ]; then exit 1; fi\n"
                "exit 88\n", encoding="utf-8",
            )
            for executable in (ha, docker):
                executable.chmod(0o700)
            env = os.environ.copy()
            env["PATH"] = str(directory) + os.pathsep + env.get("PATH", "")
            code = SCRIPT.read_bytes()
            run = subprocess.run(["sh", "-s", "--", "--execute-readonly"],
                                 input=code, env=env, capture_output=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stderr.decode())
            output = run.stdout.decode()
            self.assertIn("Supervisor installed: yes", output)
            self.assertIn("Supervisor state: stopped", output)
            self.assertIn("Docker dedicated App container: absent", output)
            self.assertIn("AUDIT COMPLETE v2", output)
            self.assertNotIn("TOPSECRET", output)
            self.assertNotIn("unlock_secret", output)

    def test_no_mutations_and_explicit_null_stdin_for_ha(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn(r"\\n", source)
        self.assertIn("ha apps info local_genvex_nabto_remote --raw </dev/null", source)
        self.assertIn("docker exec -i homeassistant python3 -B -c", source)
        for forbidden in ("docker start", "docker run", "docker cp",
                          "ha apps start", "ha apps install", "nabtoRpcInvoke"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
