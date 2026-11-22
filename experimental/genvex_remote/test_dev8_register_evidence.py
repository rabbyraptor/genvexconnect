"""DEV8.2 offline evidence gates: 17 RPC-readable != 17 HA-ready sensors."""
from __future__ import annotations

import unittest
from pathlib import Path

from dev8_register_evidence import (
    BASELINE_ADDRESSES, OBSERVED_CANDIDATE_RAW, SEVEN_ADDRESSES,
    EvidenceError, decode_candidate_raw_batch, inventory,
    proposed_entity_keys,
)
from optima270_source_only import list_source_only_candidates
from seven_read_plan_v2_draft import ORDERED_ADDRESSES, ORDERED_KEYS
from verified_read_plan import plan_current_verified_read
from capability_catalog import OPTIMA_270


class RegisterEvidenceTests(unittest.TestCase):
    def test_17_unique_source_grounded_readable_addresses(self):
        rows = inventory()
        self.assertEqual(len(rows), 17)
        self.assertEqual(len({(row.object_id, row.address) for row in rows}), 17)
        self.assertTrue(all(row.object_id == 0 for row in rows))
        self.assertEqual(
            tuple(row.address for row in rows),
            (20, 21, 22, 23, 26, 24, 18, 19, 35, 36, 41, 42,
             53, 40, 114, 115, 50),
        )
        self.assertEqual(
            tuple(row.key for row in rows[5:]),
            tuple(entry.key for entry in list_source_only_candidates()),
        )

    def test_five_deployed_only_and_two_optional_candidates(self):
        rows = inventory()
        ready = [row for row in rows if row.ready_for_ha]
        fans = [row for row in rows if row.candidate_for_fan_projection]
        self.assertEqual(len(ready), 5)
        self.assertEqual(len(fans), 2)
        self.assertEqual(tuple(row.address for row in ready), BASELINE_ADDRESSES)
        self.assertEqual(tuple(row.address for row in fans), (18, 19))
        self.assertEqual(
            {row.semantic_evidence for row in fans},
            {"app_correlated_not_simultaneous"},
        )
        self.assertTrue(all(not row.ready_for_ha for row in rows[5:]))

    def test_ten_other_candidates_are_only_raw_observations(self):
        unresolved = [
            row for row in inventory()
            if not row.ready_for_ha and not row.candidate_for_fan_projection
        ]
        self.assertEqual(len(unresolved), 10)
        self.assertEqual(
            {row.address for row in unresolved},
            {24, 35, 36, 41, 42, 53, 40, 114, 115, 50},
        )
        self.assertTrue(all(
            row.semantic_evidence == "source_only_unverified"
            and row.read_evidence == "steamdeck_twelve_once"
            for row in unresolved
        ))
        self.assertEqual(
            next(row.sample_raw for row in unresolved if row.address == 24),
            0,
        )

    def test_archival_raw_samples_preserve_values_not_physical_states(self):
        raw = decode_candidate_raw_batch(OBSERVED_CANDIDATE_RAW)
        self.assertEqual(len(raw), 12)
        self.assertEqual(raw["fan_duty_supply"], 6000)
        self.assertEqual(raw["fan_duty_extract"], 5800)
        self.assertEqual(raw["fan_rpm_supply"], 2432)
        self.assertEqual(raw["fan_rpm_extract"], 2268)
        self.assertEqual(raw["frost_protection_temp"], 0)
        self.assertEqual(raw["alarm_word_1_raw"], 0)
        self.assertEqual(raw["rotor_rpm"], 10)
        self.assertIs(type(raw["bypass_active_raw"]), int)
        self.assertIs(type(raw["alarm_word_2_raw"]), int)

    def test_raw_batch_requires_exact_signed_int16_shape(self):
        good = OBSERVED_CANDIDATE_RAW
        cases = (
            good[:-1], good + (1,), [],
            tuple(True if i == 3 else v for i, v in enumerate(good)),
            tuple("0" if i == 3 else v for i, v in enumerate(good)),
            tuple(32768 if i == 3 else v for i, v in enumerate(good)),
            tuple(-32769 if i == 3 else v for i, v in enumerate(good)),
            tuple(0.0 if i == 3 else v for i, v in enumerate(good)),
            "0" * len(good), None, {},
        )
        for case in cases:
            with self.subTest(case=repr(case)[:50]), self.assertRaises(EvidenceError):
                decode_candidate_raw_batch(case)
        minimal = [-32768] * 12
        self.assertEqual(
            decode_candidate_raw_batch(minimal)["rotor_rpm"], -32768,
        )

    def test_five_default_projection_and_seven_offline_candidate(self):
        five = proposed_entity_keys()
        seven = proposed_entity_keys(include_unreleased_fan_pair=True)
        self.assertEqual(len(five), 5)
        self.assertEqual(len(seven), 7)
        self.assertEqual(seven[:5], five)
        self.assertEqual(tuple(seven), ORDERED_KEYS)
        self.assertEqual(SEVEN_ADDRESSES, ORDERED_ADDRESSES)
        self.assertEqual(
            tuple(address for _, address in
                  plan_current_verified_read(OPTIMA_270).datapoints),
            BASELINE_ADDRESSES,
        )
        self.assertFalse(set(seven) & {
            "alarm_word_1_raw", "alarm_word_2_raw", "bypass_active_raw",
            "frost_protection_temp", "fan_rpm_supply", "fan_rpm_extract",
            "rotor_rpm", "reheat_pwm", "preheat_pwm",
        })

    def test_projection_opt_in_rejects_non_boolean_input(self):
        for invalid in (0, 1, None, "true", [], {}):
            with self.subTest(input=repr(invalid)), self.assertRaises(EvidenceError):
                proposed_entity_keys(include_unreleased_fan_pair=invalid)

    def test_module_is_inert_and_never_enables_unverified_reads(self):
        source = Path(__file__).with_name("dev8_register_evidence.py").read_text()
        for banned in (
            "nabtoRpcInvoke", "asyncio.create_subprocess", "import requests",
            "socket.connect", "get_supervisor_client", "RPC_ID = 42",
        ):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
