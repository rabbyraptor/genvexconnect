"""Read-only synthetic App mount/UID attestation regressions (offline only)."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/verify_haos_remote_mount_uid_diagnostic_v1.sh"
HOST_DATA = "/mnt/data/supervisor/apps/data/local_genvex_nabto_remote"


class MountUidDiagnosticTests(unittest.TestCase):
    def test_shell_syntax_and_preflight(self):
        syntax = subprocess.run(["sh", "-n", str(SCRIPT)], capture_output=True)
        self.assertEqual(syntax.returncode, 0, syntax.stderr.decode())
        result = subprocess.run(
            ["sh", str(SCRIPT), "--preflight"],
            text=True, capture_output=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS: inert preflight", result.stdout)

    def simulate(self, *, state="started", mode="bridge", published="null",
                 mount_ok=True, http_ok=True, uid="0"):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "app-data"
            data.mkdir(mode=0o755)
            data.chmod(0o755)
            ha = root / "ha"
            ha.write_text(
                "#!/bin/sh\n"
                "cat >/dev/null\n"
                "printf '%s\\n' '  name: unlock_secret' '  value: SECRET' "
                f"'state: {state}' 'boot: manual' 'version: 0.1.0-dev1'\n"
            )
            docker = root / "docker"
            expected = str(data) if mount_ok else "/other-directory"
            docker.write_text(
                "#!/bin/sh\n"
                "case \"$1\" in\n"
                "  inspect)\n"
                "    if [ \"$5\" != --format ]; then exit 0; fi\n"
                "    case \"$6\" in\n"
                "      *NetworkMode*) printf '%s\\n' \"$FAKE_MODE\" ;;\n"
                "      *State.Running*) echo true ;;\n"
                "      *PortBindings*) printf '%s\\n' \"$FAKE_PORTS\" ;;\n"
                f"      *Mounts*) printf '%s\\n' '{expected}' ;;\n"
                "      *) exit 9 ;;\n"
                "    esac ;;\n"
                "  exec)\n"
                "    if [ \"$2\" = homeassistant ]; then\n"
                "      [ \"$FAKE_HTTP\" = yes ] || exit 8\n"
                "      echo 'PASS: Core receives synthetic-only diagnostic; snapshot disabled'\n"
                "    elif [ \"$3\" = stat ]; then echo 755:0:0\n"
                "    elif [ \"$3\" = id ]; then printf '%s\\n' \"$FAKE_UID\"\n"
                "    else exit 9; fi ;;\n"
                "  *) exit 9 ;;\n"
                "esac\n"
            )
            stat = root / "stat"
            stat.write_text("#!/bin/sh\\necho 755:0:0\\n")
            for exe in (ha, docker, stat):
                exe.chmod(0o700)
            env = os.environ.copy()
            env["PATH"] = str(root) + os.pathsep + env.get("PATH", "")
            env["FAKE_MODE"] = mode
            env["FAKE_PORTS"] = published
            env["FAKE_HTTP"] = "yes" if http_ok else "no"
            env["FAKE_UID"] = uid
            script = SCRIPT.read_text().replace(HOST_DATA, str(data))
            return subprocess.run(
                ["sh", "-s", "--", "--execute-readonly"],
                input=script, capture_output=True, text=True, env=env, timeout=10
            )

    def test_valid_diagnostic_mount_identity(self):
        result = self.simulate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ATTESTATION COMPLETE", result.stdout)
        self.assertNotIn("SECRET", result.stdout)

    def test_stopped_app_refused(self):
        result = self.simulate(state="stopped")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BLOCKED", result.stdout)

    def test_host_network_refused(self):
        result = self.simulate(mode="host")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("host network", result.stdout)

    def test_published_port_refused(self):
        result = self.simulate(published='{"18275/tcp":{}}')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("publishes", result.stdout)

    def test_wrong_mount_refused(self):
        result = self.simulate(mount_ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("mount mismatch", result.stdout)

    def test_real_snapshot_or_no_diagnostic_refused(self):
        result = self.simulate(http_ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("diagnostic-only App not verified", result.stdout)

    def test_other_effective_uid_refused(self):
        result = self.simulate(uid="65534")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("UID differs", result.stdout)

    def test_no_mutation_and_no_secret_read(self):
        source = SCRIPT.read_text()
        for forbidden in (
            "ha apps start", "ha apps stop", "ha apps install", "docker start",
            "docker run", "chmod ", "chown ", "nabtoRpcInvoke",
            "client.crt", "client-encrypted.key", "options.json", "ipc-token",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn('"DIAGNOSTIC_ONLY"', source)
        self.assertIn('"/v1/snapshot"', source)


if __name__ == "__main__":
    unittest.main()
