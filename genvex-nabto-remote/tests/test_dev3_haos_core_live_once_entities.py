"""Credential-free launcher contracts for the one-RPC HA entity-class probe."""
from __future__ import annotations

import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import haos_core_live_entity_once_operator as op


class EntityProbeOperatorTests(unittest.TestCase):
    def test_in_memory_core_script_exact_components_and_no_secrets(self):
        source = {name: "pass\n" for name in op.MODULES}
        text = op.build_core_client(source)
        self.assertEqual(text.count(op.SUCCESS), 1)
        self.assertIn('phase = "HA_IMPORT"', text)
        self.assertIn("AuthenticatedSnapshotReader", text)
        self.assertIn("GenvexRemoteCoordinator", text)
        self.assertIn("GenvexRemoteSensor", text)
        self.assertNotIn("dummy-unlock-secret", text)
        self.assertNotIn("dummy-identity@example.invalid", text)

    def test_invalid_source_set_never_generates_core_probe(self):
        for sources in ({}, {"const": "pass\n"}, {"evil": "pass\n"}):
            with self.subTest(sources=sources), self.assertRaises(ValueError):
                op.build_core_client(sources)

    def test_staging_accepts_only_five_root_checked_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            component = stage / "ha_component"
            component.mkdir()
            for name in op.MODULES:
                (component / (name + ".py")).write_text(
                    "from __future__ import annotations\n",
                    encoding="utf-8",
                )
            with patch.object(op, "STAGING", stage), \
                 patch.object(op, "COMPONENT", component), \
                 patch.object(op.base, "check_file") as check:
                result = op.read_reviewed_sources()
                self.assertEqual(set(result), set(op.MODULES))
                self.assertEqual(check.call_count, 2 + len(op.MODULES))
                (component / "extra.py").write_text("pass\n")
                with self.assertRaises(ValueError):
                    op.read_reviewed_sources()

    def test_success_only_after_underlying_bounded_operator_passes(self):
        sources = {name: "pass\n" for name in op.MODULES}
        original = op.base.CORE_CLIENT
        phases = op.base.CORE_FAILURE_PHASES
        try:
            with patch.object(op, "read_reviewed_sources", return_value=sources), \
                 patch.object(op.base, "main", return_value=0), \
                 patch.object(sys, "argv", ["operator"]), \
                 patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(op.main(), 0)
                self.assertIn("GenvexRemoteCoordinator", op.base.CORE_CLIENT)
                self.assertIn("HA_COORDINATOR", op.base.CORE_FAILURE_PHASES)
                self.assertIn("PASS: real snapshot validated", output.getvalue())
            with patch.object(op, "read_reviewed_sources", return_value=sources), \
                 patch.object(op.base, "main", return_value=1), \
                 patch.object(sys, "argv", ["operator"]), \
                 patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(op.main(), 1)
                self.assertNotIn("PASS:", output.getvalue())
        finally:
            op.base.CORE_CLIENT = original
            op.base.CORE_FAILURE_PHASES = phases

    def test_rejects_args_without_loading_sources(self):
        with patch.object(sys, "argv", ["operator", "--poll"]), \
             patch.object(op, "read_reviewed_sources") as source, \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(op.main(), 1)
            source.assert_not_called()
            self.assertIn("BLOCKED: unsupported options", output.getvalue())


if __name__ == "__main__":
    unittest.main()
