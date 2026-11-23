"""Offline release gate regression without Home Assistant or live gateway."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/remote_release_gate.py"
spec = importlib.util.spec_from_file_location("remote_release_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class RemoteReleaseGateTests(unittest.TestCase):
    def test_one_gate_owns_all_required_source_checks(self):
        arguments = {name: argv for name, argv in gate.CHECKS}
        self.assertEqual(set(arguments), {
            "repository_links", "marketplace_scope", "runtime_parity",
            "option_contracts", "entity_localizations",
        })
        self.assertEqual(arguments["runtime_parity"][-1], "--check")
        self.assertEqual(arguments["entity_localizations"][-1], "--check")
        self.assertEqual(gate.ROOT, ROOT)

    def test_marketplace_scope_checks_only_existing_lan_package(self):
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location(
            "marketplace_scope", ROOT / "scripts/check_marketplace_scope.py"
        )
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        module.check()

    def test_failed_source_check_stops_without_running_followups(self):
        fake = subprocess.CompletedProcess([], 3, stdout="PRIVATE_VALUE")
        with patch.object(gate.subprocess, "run", return_value=fake) as run:
            with self.assertRaises(RuntimeError):
                gate.validate_sources()
        self.assertEqual(run.call_count, 1)
        self.assertIs(run.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertIs(run.call_args.kwargs["stderr"], subprocess.STDOUT)

    def test_successful_source_checks_reuse_one_gate(self):
        fake = subprocess.CompletedProcess([], 0, stdout="PASS")
        with patch.object(gate.subprocess, "run", return_value=fake) as run:
            gate.validate_sources()
        self.assertEqual(run.call_count, len(gate.CHECKS))


if __name__ == "__main__":
    unittest.main()
