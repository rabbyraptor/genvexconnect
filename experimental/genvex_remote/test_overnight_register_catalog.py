"""Offline checks for the one authored DEV9 register catalog and its projections."""
from __future__ import annotations

from pathlib import Path
import unittest

from register_catalog import (
    RPC42_FAN_LEVEL, RPC45_ALL, RPC45_BASELINE, RPC45_OPTIONAL,
    RPC45_BY_ADDRESS,
)
from sensor_model import SENSORS
from raw_registers_v3 import ALL_REGISTERS, BASE_ADDRESSES, OPTIONAL_ADDRESSES


class RegisterCatalogTests(unittest.TestCase):
    def test_exact_baseline_and_optional_order(self):
        self.assertEqual(
            tuple(spec.address for spec in RPC45_BASELINE),
            (20, 21, 22, 23, 26),
        )
        self.assertEqual(
            tuple(spec.address for spec in RPC45_OPTIONAL),
            (24, 18, 19, 35, 36, 41, 42, 53, 40, 114, 115, 50),
        )
        self.assertEqual(tuple(spec.address for spec in SENSORS), BASE_ADDRESSES)
        self.assertEqual(
            ALL_REGISTERS,
            tuple((spec.key, spec.address) for spec in RPC45_ALL),
        )
        self.assertEqual(
            OPTIONAL_ADDRESSES,
            tuple(spec.address for spec in RPC45_OPTIONAL),
        )
        self.assertEqual(len(RPC45_BY_ADDRESS), 17)

    def test_stage_metadata_and_evidence_boundaries(self):
        self.assertEqual(
            (RPC42_FAN_LEVEL.object_id, RPC42_FAN_LEVEL.address,
             RPC42_FAN_LEVEL.minimum, RPC42_FAN_LEVEL.maximum),
            (0, 7, 0, 4),
        )
        self.assertEqual(
            tuple(spec.evidence for spec in RPC45_BASELINE),
            ("validated_scaled_measurement",) * 5,
        )
        for address in (18, 19):
            spec = RPC45_BY_ADDRESS[address]
            self.assertEqual(spec.evidence, "source_model_official_ui_match")
            self.assertEqual(spec.display_divisor, 100)
            self.assertIn("not measured airflow", spec.note)
        for address in (35, 36, 114, 115, 50):
            spec = RPC45_BY_ADDRESS[address]
            self.assertEqual(spec.evidence, "source_model_only")
            self.assertIsNone(spec.display_divisor)
            self.assertTrue(spec.note)

    def test_canonical_source_matches_both_shipping_projections(self):
        root = Path(__file__).resolve().parents[2]
        canonical = root / "experimental/genvex_remote/register_catalog.py"
        for target in (
            root / "genvex-nabto-remote/runtime/register_catalog.py",
            root / "experimental/home_assistant/custom_components/genvex_remote/register_catalog.py",
        ):
            with self.subTest(path=target):
                self.assertEqual(canonical.read_bytes(), target.read_bytes())


if __name__ == "__main__":
    unittest.main()
