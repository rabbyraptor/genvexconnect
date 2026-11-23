"""DEV8.3: strict all-17-raw schema, failure isolation, compatibility."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from copy import deepcopy
import unittest

from raw_registers_v3 import (
    ALL_REGISTERS, ALL_KEYS, BASE_ADDRESSES, BASE_KEYS, OPTIONAL_ADDRESSES,
    OPTIONAL_KEYS, make_raw_v3, parse_raw_v3,
)
from snapshot_contract import SnapshotError, parse_snapshot

DEVICE = "123456789012"
BASE = (368, 308, 322, 378, 67)
EXTRA = (0, 6000, 5800, 2432, 2268, 0, 0, 0, 0, 0, 0, 10)


class RawV3Tests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.doc = make_raw_v3(
            device_id=DEVICE, measured_at=self.now,
            baseline_raw=BASE, additional_raw=EXTRA,
        )

    def test_exact_source_backed_seventeen_address_order(self):
        self.assertEqual(len(ALL_REGISTERS), 17)
        self.assertEqual(len(set(ALL_KEYS)), 17)
        self.assertEqual(BASE_ADDRESSES, (20, 21, 22, 23, 26))
        self.assertEqual(
            OPTIONAL_ADDRESSES,
            (24, 18, 19, 35, 36, 41, 42, 53, 40, 114, 115, 50),
        )

    def test_raws_are_signed_int16_with_no_inferred_physical_units(self):
        base, raw = parse_raw_v3(self.doc, expected_device_id=DEVICE, now=self.now)
        self.assertEqual(tuple(raw), ALL_KEYS)
        self.assertEqual(tuple(raw[key] for key in BASE_KEYS), BASE)
        self.assertEqual(tuple(raw[key] for key in OPTIONAL_KEYS), EXTRA)
        self.assertEqual(raw["frost_protection_temp"], 0)
        self.assertEqual(raw["alarm_word_1_raw"], 0)
        self.assertEqual(raw["rotor_rpm"], 10)
        self.assertEqual(type(raw["bypass_active_raw"]), int)
        self.assertEqual(base["supply_air"], 6.8)
        self.assertEqual(base["humidity"], 67.0)

    def test_missing_optional_group_preserves_v1_measurements(self):
        doc = make_raw_v3(
            device_id=DEVICE, measured_at=self.now,
            baseline_raw=BASE, additional_raw=None,
        )
        base, raw = parse_raw_v3(doc, expected_device_id=DEVICE, now=self.now)
        self.assertEqual(tuple(raw), BASE_KEYS)
        self.assertEqual(doc["optional"]["raw_registers"], {})
        self.assertEqual(base, self.doc["values"])
        # v1 clients require only this strict projection; a v3 payload
        # MUST NOT be passed directly as a v1 response.
        legacy = {key: self.doc[key] for key in (
            "schema_version", "device_id", "timestamp_utc", "health", "values"
        )}
        legacy["schema_version"] = 1
        self.assertEqual(
            parse_snapshot(legacy, expected_device_id=DEVICE, now=self.now),
            base,
        )

    def test_raw_values_are_not_exposed_on_v1_schema(self):
        with self.assertRaises(SnapshotError):
            parse_snapshot(self.doc, expected_device_id=DEVICE, now=self.now)

    def test_incomplete_invalid_or_extra_optional_is_rejected(self):
        bad_samples = (
            dict(list(self.doc["optional"]["raw_registers"].items())[:-1]),
            {"unknown": 17},
            {k: 0 for k in OPTIONAL_KEYS} | {"secret": 1},
            {**self.doc["optional"]["raw_registers"], "rotor_rpm": True},
            {**self.doc["optional"]["raw_registers"], "rotor_rpm": 32768},
            {**self.doc["optional"]["raw_registers"], "rotor_rpm": "10"},
        )
        for raw in bad_samples:
            with self.subTest(raw=str(raw)[:60]):
                doc = deepcopy(self.doc)
                doc["optional"]["raw_registers"] = raw
                with self.assertRaises(SnapshotError):
                    parse_raw_v3(doc, expected_device_id=DEVICE, now=self.now)

    def test_invalid_five_raw_or_scaled_baseline_rejected(self):
        doc = deepcopy(self.doc)
        doc["raw_values"]["humidity"] = 68
        with self.assertRaises(SnapshotError):
            parse_raw_v3(doc, expected_device_id=DEVICE, now=self.now)
        doc = deepcopy(self.doc)
        doc["raw_values"]["humidity"] = True
        with self.assertRaises(SnapshotError):
            parse_raw_v3(doc, expected_device_id=DEVICE, now=self.now)
        doc = deepcopy(self.doc)
        del doc["raw_values"]["humidity"]
        with self.assertRaises(SnapshotError):
            parse_raw_v3(doc, expected_device_id=DEVICE, now=self.now)

    def test_schema_identity_timestamp_and_whitelist(self):
        for change in (
            {"schema_version": 2},
            {"schema_version": True},
            {"device_id": "999999999999"},
            {"timestamp_utc": (self.now - timedelta(minutes=4)).isoformat()},
            {"health": "stale"},
        ):
            doc = deepcopy(self.doc)
            doc.update(change)
            with self.subTest(change=change), self.assertRaises(SnapshotError):
                parse_raw_v3(doc, expected_device_id=DEVICE, now=self.now)
        doc = deepcopy(self.doc)
        doc["private_identity"] = "SENSITIVE"
        with self.assertRaises(SnapshotError):
            parse_raw_v3(doc, expected_device_id=DEVICE, now=self.now)

    def test_raw_batch_rejects_missing_extra_and_nonint(self):
        for extra in (EXTRA[:-1], EXTRA+(1,), EXTRA[:3]+("5800",)+EXTRA[4:],
                      EXTRA[:3]+(True,)+EXTRA[4:]):
            with self.assertRaises(SnapshotError):
                make_raw_v3(device_id=DEVICE, measured_at=self.now,
                            baseline_raw=BASE, additional_raw=extra)

    def test_five_baseline_mandatory_even_if_optional_valid(self):
        with self.assertRaises(SnapshotError):
            make_raw_v3(device_id=DEVICE, measured_at=self.now,
                        baseline_raw=BASE[:-1], additional_raw=EXTRA)


if __name__ == "__main__":
    unittest.main()
