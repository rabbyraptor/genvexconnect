"""Offline host-network prevention test for read-only HAOS IPC audit script."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/audit_haos_v2_ipc_network_gate_v1.sh"


class HAOSV2NetworkGateTests(unittest.TestCase):
    def run_fake(self, mode, *, remote_present=True, ports="null"):
        with tempfile.TemporaryDirectory() as folder:
            shim = Path(folder) / "docker"
            shim.write_text("""#!/bin/sh
case "$1" in
 inspect)
    case "$*" in
        *homeassistant*) exit 0 ;;
        *app_local_genvex_nabto_runtime_test*)
            case "$*" in *--format*) echo host ;; esac
            exit 0 ;;
        *app_local_genvex_nabto_remote*)
            if [ "$TEST_APP_PRESENT" = no ]; then exit 1; fi
            case "$*" in
                *NetworkMode*) echo "$TEST_NET_MODE" ;;
                *PortBindings*) echo "$TEST_PORT_BINDINGS" ;;
            esac
            exit 0 ;;
    esac ;;
 exec)
    case "$*" in
        *homeassistant*) echo "Core -> dedicated remote App DNS: RESOLVES"; exit 0 ;;
    esac ;;
esac
exit 87
""", encoding="utf-8")
            shim.chmod(0o700)
            env = os.environ.copy()
            env.update(PATH=folder + os.pathsep + env.get("PATH", ""),
                       TEST_NET_MODE=mode,
                       TEST_APP_PRESENT="yes" if remote_present else "no",
                       TEST_PORT_BINDINGS=ports)
            return subprocess.run(["sh", str(SCRIPT), "--execute-readonly"],
                                  env=env, capture_output=True, text=True, timeout=10)

    def test_syntax_and_inert_preflight(self):
        self.assertEqual(subprocess.run(["sh", "-n", str(SCRIPT)]).returncode, 0)
        result = subprocess.run(["sh", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("PASS: inert preflight", result.stdout)

    def test_never_creates_network_or_calls_rpc(self):
        source = SCRIPT.read_text()
        self.assertNotIn("docker run", source)
        self.assertNotIn("docker network create", source)
        self.assertNotIn("docker start", source)
        self.assertNotIn("docker cp", source)
        self.assertNotIn("curl ", source)
        self.assertNotIn("nabtoRpcInvoke", source)
        self.assertIn("socket.getaddrinfo", source)
        self.assertIn("docker exec", source)
        self.assertIn("python3 -B -c", source)

    def test_not_installed_is_informational(self):
        result = self.run_fake("hassio", remote_present=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("NOT READY", result.stdout)

    def test_host_and_default_bridge_are_blocked(self):
        for mode in ("host", "bridge", "none"):
            with self.subTest(mode=mode):
                result = self.run_fake(mode)
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertIn("BLOCKED", result.stdout)
                self.assertNotIn("DNS: RESOLVES", result.stdout)

    def test_host_port_publish_is_blocked(self):
        result = self.run_fake("hassio", ports='{"18275/tcp":[{"HostIp":"0.0.0.0","HostPort":"18275"}]}')
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("host port bindings", result.stdout)

    def test_dedicated_network_is_only_conditional(self):
        result = self.run_fake("hassio")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("MANUAL REVIEW REQUIRED", result.stdout)
        self.assertIn("DNS: RESOLVES", result.stdout)


if __name__ == "__main__":
    unittest.main()
