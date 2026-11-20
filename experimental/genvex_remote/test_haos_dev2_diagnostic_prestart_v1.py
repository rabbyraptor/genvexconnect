"""Synthetic tests for the read-only post-dev2 diagnostic gate."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/audit_haos_dev2_diagnostic_prestart_from_deck_v1.py"
spec = importlib.util.spec_from_file_location("read_only_diagnostic_gate", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def info(**overrides):
    data = {
        "version": "0.1.0-dev2",
        "state": "stopped",
        "boot": "manual",
        "options": {
            "device_id": "", "identity": "", "unlock_secret": "",
            "ipc_token": "", "diagnostic_only": False, "poll_seconds": 60,
        },
    }
    opts = overrides.pop("options", None)
    data.update(overrides)
    if opts is not None:
        data["options"].update(opts)
    return json.dumps({"result": "ok", "data": data})


class DiagnosticReadOnlyGateTests(unittest.TestCase):
    def test_valid_baseline(self):
        self.assertEqual(mod.parse_info(info()), {"poll_seconds": 60})

    def test_rejects_any_nonempty_credential(self):
        for key in mod.FIELDS:
            with self.subTest(key=key), self.assertRaises(ValueError):
                mod.parse_info(info(options={key: "FAKE-NOT-A-REAL-SECRET"}))

    def test_rejects_invalid_lifecycle_and_option_flags(self):
        for override in (
            {"state": "started"}, {"version": "0.1.0-dev1"},
            {"boot": "auto"}, {"options": {"diagnostic_only": True}},
            {"options": {"poll_seconds": 1}},
            {"options": {"poll_seconds": True}},
            {"options": {"diagnostic_only": "false"}},
        ):
            with self.subTest(override=override), self.assertRaises(ValueError):
                mod.parse_info(info(**override))

    def test_preflight_never_uses_ssh(self):
        with patch.object(mod, "run_remote", side_effect=AssertionError):
            self.assertEqual(mod.main(["--preflight"]), 0)

    def test_execution_uses_only_three_read_only_remote_queries(self):
        responses = [info(), "PRIVATE_PATHS_ABSENT\n", "REMOTE_APP_STOPPED\n"]
        with patch.object(mod, "run_remote", side_effect=responses) as remote:
            self.assertEqual(mod.main(["--execute-readonly"]), 0)
        self.assertEqual(remote.call_count, 3)
        commands = [call.args[0] for call in remote.call_args_list]
        self.assertIn("ha apps info", commands[0])
        self.assertIn("--raw-json", commands[0])
        self.assertIn("test ! -e", commands[1])
        self.assertIn("docker inspect", commands[2])
        self.assertNotIn("apps start", " ".join(commands))
        self.assertNotIn("apps stop", " ".join(commands))
        self.assertNotIn("apps options", " ".join(commands))

    def test_refusal_does_not_run_path_or_docker_queries(self):
        with patch.object(mod, "run_remote", return_value=info(state="started")) as remote:
            self.assertEqual(mod.main(["--execute-readonly"]), 1)
        remote.assert_called_once()

    def test_script_does_not_contain_mutations_or_private_reads(self):
        source = SOURCE.read_text()
        for forbidden in (
            "ha apps start", "ha apps stop", "ha store reload",
            "ha apps update", "docker exec", "curl ", "cat /mnt/data",
            "read_text(", "open('/mnt/data",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
