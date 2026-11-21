"""Fake-only host-operator contracts for HA Core private Docker IPC probe."""
from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import haos_core_ipc_network_operator as op


def fake_core_network(networks):
    return json.dumps([{
        "State": {"Running": True},
        "NetworkSettings": {"Networks": {key: {} for key in networks}},
    }]).encode("utf-8")


def fake_docker_network():
    return json.dumps([{"Driver": "bridge", "Scope": "local"}]).encode("utf-8")


class CoreIPCTests(unittest.TestCase):
    def test_prefers_hassio_network_without_modifying_core(self):
        calls = []

        def runner(args, **kwargs):
            calls.append(args)
            if args[:3] == ["docker", "inspect", "--type"]:
                return Mock(returncode=0, stdout=fake_core_network(["hassio", "extra"]))
            if args[:3] == ["docker", "network", "inspect"]:
                return Mock(returncode=0, stdout=fake_docker_network())
            raise AssertionError(f"unexpected: {args}")

        with patch.object(op, "run", side_effect=runner):
            self.assertEqual(op.select_core_network(), "hassio")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1], ["docker", "network", "inspect", "hassio"])

    def test_missing_or_ambiguous_private_network_rejected(self):
        for networks in (["bridge"], ["other-a", "other-b"]):
            with self.subTest(networks=networks), \
                 patch.object(op, "run", return_value=Mock(
                     returncode=0, stdout=fake_core_network(networks)
                 )):
                with self.assertRaises(RuntimeError):
                    op.select_core_network()

    def test_one_fake_private_server_and_core_exec_then_forced_cleanup(self):
        commands = []
        success = (b"PASS: HA Core container reached authenticated private IPC;"
                   b" 401/200/404\n")

        def runner(args, **kwargs):
            commands.append((list(args), kwargs))
            if args[:3] == ["docker", "run", "-d"]:
                return Mock(returncode=0, stdout=b"container-id\n")
            if args[:3] == ["docker", "exec", "-i"]:
                return Mock(returncode=0, stdout=success)
            if args[:3] == ["docker", "rm", "-f"]:
                return Mock(returncode=0, stdout=b"")
            raise AssertionError(f"unexpected: {args}")

        with patch.object(op.os, "geteuid", return_value=0), \
             patch.object(op, "check_file"), \
             patch.object(op, "checked_image", return_value="sha256:" + "a" * 64), \
             patch.object(op, "select_core_network", return_value="hassio"), \
             patch.object(op, "core_network_mode", return_value="bridge"), \
             patch.object(op.secrets, "token_hex", return_value="abcdef1234"), \
             patch.object(op, "run", side_effect=runner), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(op.operator(), 0)
        self.assertEqual(len(commands), 3)
        command, _ = commands[0]
        self.assertEqual(command[command.index("--network") + 1], "hassio")
        self.assertEqual(command[command.index("--network-alias") + 1],
                         "genvex-dev3-ipc-abcdef1234")
        self.assertNotIn("-p", command)
        self.assertNotIn("--publish", command)
        self.assertIn("--read-only", command)
        self.assertIn("--cap-drop", command)
        self.assertIn("--log-driver", command)
        self.assertEqual(commands[1][0][:5],
                         ["docker", "exec", "-i", "homeassistant", "python3"])
        self.assertEqual(commands[1][0][-1], "genvex-dev3-ipc-abcdef1234")
        self.assertIn(b"check(None, \"/v1/snapshot\", 401)",
                      commands[1][1]["input"])
        self.assertEqual(commands[2][0],
                         ["docker", "rm", "-f", "genvex-dev3-ipc-net-abcdef1234"])
        self.assertIn("PASS: HA Core container", output.getvalue())

    def test_failure_does_not_leave_server_running(self):
        commands = []

        def runner(args, **kwargs):
            commands.append(args)
            if args[:3] == ["docker", "run", "-d"]:
                return Mock(returncode=0, stdout=b"container-id")
            if args[:3] == ["docker", "exec", "-i"]:
                return Mock(returncode=1, stdout=b"", stderr=b"secret ignored")
            if args[:3] == ["docker", "rm", "-f"]:
                return Mock(returncode=0, stdout=b"")
            raise AssertionError(args)

        with patch.object(op.os, "geteuid", return_value=0), \
             patch.object(op, "check_file"), \
             patch.object(op, "checked_image", return_value="sha256:" + "a" * 64), \
             patch.object(op, "select_core_network", return_value="hassio"), \
             patch.object(op, "run", side_effect=runner), \
             patch.object(op.time, "sleep"), \
             patch.object(sys, "argv", ["haos_core_ipc_network_operator.py"]), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(op.main(), 1)
        self.assertEqual(sum(x[:3] == ["docker", "exec", "-i"] for x in commands), 5)
        self.assertEqual(commands[-1][:3], ["docker", "rm", "-f"])
        self.assertNotIn("secret ignored", output.getvalue())

    def test_host_network_core_uses_hassio_bridge(self):
        calls = []
        def runner(args, **kwargs):
            calls.append(args)
            if args[:3] == ["docker", "inspect", "--type"]:
                return Mock(returncode=0, stdout=json.dumps([{
                    "State": {"Running": True},
                    "HostConfig": {"NetworkMode": "host"},
                    "NetworkSettings": {"Networks": {"host": {}}},
                }]).encode())
            if args[:3] == ["docker", "network", "inspect"]:
                return Mock(returncode=0, stdout=fake_docker_network())
            raise AssertionError(args)
        with patch.object(op, "run", side_effect=runner):
            self.assertEqual(op.select_core_network(), "hassio")
        self.assertEqual(calls[-1], ["docker", "network", "inspect", "hassio"])

    def test_host_core_uses_container_private_ip(self):
        commands = []
        success = (b"PASS: HA Core container reached authenticated private IPC;"
                   b" 401/200/404\\n")
        def runner(args, **kwargs):
            commands.append(args)
            if args[:3] == ["docker", "run", "-d"]:
                return Mock(returncode=0, stdout=b"cid")
            if args[:3] == ["docker", "inspect", "--type"]:
                return Mock(returncode=0, stdout=json.dumps([{
                    "NetworkSettings": {"Networks": {"hassio": {
                        "IPAddress": "172.30.33.123",
                    }}},
                }]).encode())
            if args[:3] == ["docker", "exec", "-i"]:
                return Mock(returncode=0, stdout=success)
            if args[:3] == ["docker", "rm", "-f"]:
                return Mock(returncode=0, stdout=b"")
            raise AssertionError(args)
        with patch.object(op.os, "geteuid", return_value=0), \\
             patch.object(op, "check_file"), \\
             patch.object(op, "checked_image", return_value="sha256:" + "a" * 64), \\
             patch.object(op, "select_core_network", return_value="hassio"), \\
             patch.object(op, "core_network_mode", return_value="host"), \\
             patch.object(op, "run", side_effect=runner), \\
             patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(op.operator(), 0)
        self.assertEqual(commands[2][-1], "172.30.33.123")
        self.assertEqual(commands[-1][:3], ["docker", "rm", "-f"])


if __name__ == "__main__":
    unittest.main()
