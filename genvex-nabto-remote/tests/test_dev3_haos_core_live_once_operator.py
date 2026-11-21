"""Offline one-shot operator contracts: host-network Core to real RPC45 IPC."""
from __future__ import annotations

from datetime import datetime, timezone
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))
sys.path.insert(0, str(BASE / "runtime"))
import haos_core_live_once_operator as op
from polling_http_server import SnapshotHTTPServer

DEVICE = "123456789012"
TOKEN = "T" * 43
PASS_LINE = b"PASS: one real Genvex RPC45 snapshot reached HA Core over private HTTP\n"
SETTINGS = {"device_id": DEVICE, "identity": "dummy@example.invalid",
            "unlock_secret": "not-real"}


class OperatorTests(unittest.TestCase):
    def test_real_http_parser_against_fake_snapshot_no_sdk(self):
        """The exact stdlib Core probe speaks to the actual HTTP bridge."""
        document = {
            "schema_version": 1, "device_id": DEVICE,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "health": "ok",
            "values": {
                "supply_air": 4.0, "outdoor_air": 2.0,
                "exhaust_air": 7.0, "extract_air": 6.0,
                "humidity": 52.0,
            },
        }
        service = SnapshotHTTPServer(
            bind_host="127.0.0.1", port=0,
            device_id=DEVICE, token=TOKEN,
            snapshot_provider=lambda: document,
        )
        try:
            service.start()
            payload = json.dumps({"device_id": DEVICE, "ipc_token": TOKEN}).encode() + b"\n"
            proc = subprocess.run(
                [sys.executable, "-c", op.CORE_CLIENT, "127.0.0.1",
                 str(service._server.server_address[1])],
                input=payload, capture_output=True, timeout=12, check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr.decode()[-400:])
            self.assertEqual(proc.stdout, PASS_LINE)
        finally:
            service.stop()

    def test_live_operator_keeps_secrets_out_of_docker_and_core_argv(self):
        commands = []
        pipe = io.BytesIO()

        class FakeProcess:
            stdin = pipe
            def poll(self): return None
            def wait(self, timeout): return 0

        def fake_run(args, **kwargs):
            commands.append((args, kwargs))
            if args[:3] == ["docker", "exec", "-i"]:
                return Mock(returncode=0, stdout=PASS_LINE)
            if args[:3] == ["docker", "rm", "-f"]:
                return Mock(returncode=0, stdout=b"")
            raise AssertionError(args)

        def fake_popen(args, **kwargs):
            commands.append((args, kwargs))
            return FakeProcess()

        with patch.object(op.os, "geteuid", return_value=0), \
             patch.object(op, "check_file"), \
             patch.object(op, "preflight", return_value="sha256:" + "a" * 64), \
             patch.object(op, "select_core_network", return_value="hassio"), \
             patch.object(op, "core_network_mode", return_value="host"), \
             patch.object(op, "prompt_settings",
                          return_value=json.dumps(SETTINGS).encode() + b"\n"), \
             patch.object(op.secrets, "token_urlsafe", return_value=TOKEN), \
             patch.object(op.secrets, "token_hex", return_value="abc123"), \
             patch.object(op, "private_address", return_value="172.30.33.77"), \
             patch.object(op, "run", side_effect=fake_run), \
             patch.object(op.subprocess, "Popen", side_effect=fake_popen), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(op.operator(), 0)

        self.assertEqual(len(commands), 3)
        docker_args = commands[0][0]
        core_args = commands[1][0]
        self.assertEqual(core_args[-1], "172.30.33.77")
        self.assertNotIn("-p", docker_args)
        self.assertNotIn("--publish", docker_args)
        self.assertIn("--read-only", docker_args)
        self.assertIn("--network", docker_args)
        self.assertIn("hassio", docker_args)
        self.assertEqual(commands[-1][0][:3], ["docker", "rm", "-f"])
        for command, kwargs in commands:
            rendered = repr(command)
            self.assertNotIn("not-real", rendered)
            self.assertNotIn("dummy@example.invalid", rendered)
            self.assertNotIn(TOKEN, rendered)
        self.assertEqual(json.loads(commands[1][1]["input"]), {
            "device_id": DEVICE, "ipc_token": TOKEN,
        })
        self.assertIn("PASS: one real Genvex", output.getvalue())

    def test_timeout_always_cleans_up(self):
        commands = []
        class FakeProcess:
            stdin = io.BytesIO()
            def poll(self): return None
            def wait(self, timeout): return 0
        def fake_run(args, **kwargs):
            commands.append(args)
            return Mock(returncode=0, stdout=b"")
        with patch.object(op.os, "geteuid", return_value=0), \
             patch.object(op, "check_file"), \
             patch.object(op, "preflight", return_value="sha256:" + "a" * 64), \
             patch.object(op, "select_core_network", return_value="hassio"), \
             patch.object(op, "core_network_mode", return_value="host"), \
             patch.object(op, "prompt_settings",
                          return_value=json.dumps(SETTINGS).encode() + b"\n"), \
             patch.object(op, "private_address", return_value=None), \
             patch.object(op, "run", side_effect=fake_run), \
             patch.object(op.subprocess, "Popen", return_value=FakeProcess()), \
             patch.object(op.time, "monotonic", side_effect=[0, 112]), \
             patch.object(sys, "argv", ["haos_core_live_once_operator.py"]), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(op.main(), 1)
        self.assertEqual(commands[-1][:3], ["docker", "rm", "-f"])
        self.assertIn("BLOCKED", output.getvalue())

    def test_runtime_exit_reports_only_allowlisted_category(self):
        safe = Mock(stdout=io.BytesIO(b"BLOCKED: SDK_SESSION_FAILED\\n"))
        self.assertEqual(op.classify_runtime_exit(safe).code,
                         "SDK_SESSION_FAILED")
        for output in (
            b"BLOCKED: SDK_SESSION_FAILED\\nsecret=hunter2\\n",
            b"BLOCKED: unknown-secret-code\\n",
            b"token=example-private-value\\n",
            b"BLOCKED: SDK_SESSION_FAILED\\n" + b"z" * 600,
            b"\\xff\\xfe\\n",
        ):
            with self.subTest(output_size=len(output)):
                unsafe = Mock(stdout=io.BytesIO(output))
                error = op.classify_runtime_exit(unsafe)
                self.assertEqual(error.code,
                                 "RUNTIME_EXITED_WITHOUT_SAFE_DIAGNOSTIC")
                self.assertNotIn("secret", str(error))
                self.assertNotIn("token=", str(error))

    def test_http_probe_timeout_retries_without_restarting_sdk(self):
        commands = []

        class FakeProcess:
            def __init__(self):
                self.stdin = io.BytesIO()
                self.stdout = io.BytesIO()
            def poll(self): return None
            def wait(self, timeout): return 0

        child = FakeProcess()
        def fake_run(args, **kwargs):
            commands.append((args, kwargs))
            if args[:3] == ["docker", "exec", "-i"]:
                count = sum(c[0][:3] == ["docker", "exec", "-i"]
                            for c in commands)
                if count == 1:
                    raise subprocess.TimeoutExpired(args, 14)
                return Mock(returncode=0, stdout=PASS_LINE)
            if args[:3] == ["docker", "rm", "-f"]:
                return Mock(returncode=0, stdout=b"")
            raise AssertionError(args)

        with patch.object(op.os, "geteuid", return_value=0), \\
             patch.object(op, "check_file"), \\
             patch.object(op, "preflight", return_value="sha256:" + "a" * 64), \\
             patch.object(op, "select_core_network", return_value="hassio"), \\
             patch.object(op, "core_network_mode", return_value="host"), \\
             patch.object(op, "prompt_settings",
                          return_value=json.dumps(SETTINGS).encode() + b"\\n"), \\
             patch.object(op, "private_address", return_value="172.30.33.77"), \\
             patch.object(op, "run", side_effect=fake_run), \\
             patch.object(op.subprocess, "Popen", return_value=child) as launch, \\
             patch.object(op.time, "sleep"), \\
             patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(op.operator(), 0)
        launch.assert_called_once()
        self.assertEqual(sum(c[0][:3] == ["docker", "exec", "-i"]
                             for c in commands), 2)
        self.assertEqual(commands[-1][0][:3], ["docker", "rm", "-f"])


if __name__ == "__main__":
    unittest.main()
