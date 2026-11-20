"""Offline safety tests: source-only inventory and verified-only RPC45 request plan."""
import unittest

from capability_catalog import OPTIMA_270, ControllerProfile
from model_lookup import UnknownModel
from optima270_source_only import (
    InvalidCandidate,
    OPTIMA_270_SOURCE_ONLY,
    SourceOnlyDatapoint,
    list_source_only_candidates,
)
from sensor_model import SENSORS
from verified_read_plan import (
    Rpc45Plan,
    UnsafeReadPlan,
    plan_current_verified_read,
    plan_from_numeric_ping,
)


def fake_ping(**updates):
    doc = {
        "Model": 2010, "Devicenumber": 79265, "Version": 1,
        "SlaveDevicenumber": 1, "SlaveModel": 1,
        "UserNames:": "DO_NOT_KEEP_OR_ECHO",
    }
    doc.update(updates)
    return doc


class ReadPlanSafetyTests(unittest.TestCase):
    def test_twelve_candidates_are_outside_five_verified_readings(self):
        candidates = list_source_only_candidates()
        self.assertEqual(len(candidates), 12)
        self.assertEqual(tuple(item.address for item in candidates), (
            24, 18, 19, 35, 36, 41, 42, 53, 40, 114, 115, 50
        ))
        self.assertTrue(all(item.object_id == 0 for item in candidates))
        self.assertTrue(all(item.remote_status == "source_only_unverified"
                            for item in candidates))
        self.assertEqual(
            len({r.address for r in OPTIMA_270.readings}.union(
                item.address for item in candidates
            )),
            17,
        )

    def test_verified_plan_matches_existing_ordered_rpc45_batch(self):
        plan = plan_current_verified_read(OPTIMA_270)
        self.assertEqual(plan.rpc_id, 45)
        self.assertEqual(plan.query_name, "candidate_read_datapoints.json")
        self.assertEqual(plan.semantic_keys, tuple(item.key for item in SENSORS))
        self.assertEqual(
            plan.request_body(),
            {"request": {"datapoints": [
                {"obj": 0, "address": 20},
                {"obj": 0, "address": 21},
                {"obj": 0, "address": 22},
                {"obj": 0, "address": 23},
                {"obj": 0, "address": 26},
            ], "trailer": 1}},
        )

    def test_ping_model_lookup_then_plan_does_not_leak_response(self):
        plan = plan_from_numeric_ping(fake_ping())
        self.assertEqual(len(plan.datapoints), 5)
        self.assertNotIn("DO_NOT_KEEP_OR_ECHO", repr(plan))
        self.assertNotIn("DO_NOT_KEEP_OR_ECHO", repr(plan.request_body()))

    def test_unknown_model_and_bad_ping_never_create_plan(self):
        for invalid in (
            fake_ping(Model=1141), fake_ping(Devicenumber=0),
            fake_ping(Version="1"), {},
        ):
            with self.subTest(metadata=invalid):
                with self.assertRaises(UnknownModel):
                    plan_from_numeric_ping(invalid)

    def test_manual_unknown_or_reordered_address_cannot_be_planned(self):
        good = plan_current_verified_read(OPTIMA_270)
        test_addresses = (
            ((0, 20), (0, 21), (0, 22), (0, 23), (0, 24)),
            ((0, 21), (0, 20), (0, 22), (0, 23), (0, 26)),
            ((0, 20), (0, 21), (0, 22), (0, 23)),
            ((0, 20), (0, 21), (0, 22), (0, 23), (0, 23)),
            ((0, 20), (0, 21), (0, 22), (0, True), (0, 26)),
        )
        for addresses in test_addresses:
            with self.subTest(addresses=addresses):
                with self.assertRaises(UnsafeReadPlan):
                    Rpc45Plan(good.model_key, good.semantic_keys, addresses)

    def test_not_all_source_only_candidates_are_live_read_approved(self):
        # A forged equal-looking profile must not be able to inject a
        # source-only address into the production-approved five-address plan.
        from capability_catalog import Reading
        candidate = OPTIMA_270_SOURCE_ONLY[0]
        forged = ControllerProfile(
            "optima270", "Genvex", "Optima 270", 45,
            OPTIMA_270.readings[:-1] + (
                Reading("forged_candidate", "Forged", 0, candidate.address,
                        "number", "sensor", None, evidence="source_only_unverified"),
            ),
        )
        with self.assertRaises(UnsafeReadPlan):
            plan_current_verified_read(forged)

    def test_source_only_candidate_metadata_rejects_invalid_values(self):
        for bad in (
            {"key": "BOGUS"},
            {"address": -1},
            {"address": True},
            {"scale_divisor": 0},
            {"scale_divisor": 2.5},
            {"engineering_note": None},
        ):
            with self.subTest(bad=bad):
                args = dict(key="candidate", label="Source only", address=123)
                args.update(bad)
                with self.assertRaises(InvalidCandidate):
                    SourceOnlyDatapoint(**args)


if __name__ == "__main__":
    unittest.main()
