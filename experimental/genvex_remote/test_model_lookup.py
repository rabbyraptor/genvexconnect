"""Offline 2B regression checks; no SDK or HA imports and no live access."""
import unittest

from capability_catalog import OPTIMA_270
from model_lookup import (
    DeviceMetadata,
    UnknownModel,
    parse_numeric_ping,
    planned_verified_reads,
    select_verified_remote_profile,
)


def fake_ping(**changes):
    result = {
        "Model": 2010,
        "Devicenumber": 79265,
        "Version": 1,
        "SlaveDevicenumber": 1111,
        "SlaveModel": 1,
        "Pong": 1886350951,
        "UserNames:": "private-value-which-must-not-be-retained",
    }
    result.update(changes)
    return result


class ModelLookupTests(unittest.TestCase):
    def test_source_grounded_optima270_selects_only_verified_five(self):
        metadata = parse_numeric_ping(fake_ping())
        self.assertIs(select_verified_remote_profile(metadata), OPTIMA_270)
        self.assertEqual(planned_verified_reads(fake_ping()), (
            (0, 20), (0, 21), (0, 22), (0, 23), (0, 26),
        ))

    def test_private_or_unknown_ping_fields_not_retained(self):
        metadata = parse_numeric_ping(fake_ping(**{"UserNames:": "do-not-retain"}))
        self.assertNotIn("do-not-retain", repr(metadata))
        self.assertNotIn("UserNames", repr(metadata))
        self.assertEqual(
            tuple(metadata.__dataclass_fields__.keys()),
            ("model", "device_number", "version", "slave_device_number", "slave_model"),
        )

    def test_metadata_is_numeric_and_bounded(self):
        for field in ("Model", "Devicenumber", "Version", "SlaveDevicenumber", "SlaveModel"):
            for invalid in (None, True, "2010", -1, 0x100000000, 1.0):
                with self.subTest(field=field, value=invalid):
                    with self.assertRaises(UnknownModel):
                        parse_numeric_ping(fake_ping(**{field: invalid}))

    def test_unknown_models_cannot_fallback_to_optima270(self):
        for values in (
            {"Model": 1141}, {"Devicenumber": 79266},
            {"Model": 1040}, {"Model": 2020},
        ):
            with self.subTest(values=values):
                metadata = parse_numeric_ping(fake_ping(**values))
                with self.assertRaises(UnknownModel):
                    select_verified_remote_profile(metadata)
                with self.assertRaises(UnknownModel):
                    planned_verified_reads(fake_ping(**values))

    def test_invalid_response_and_identity_fail_closed(self):
        for value in (None, [], 1, "{}", {}):
            with self.subTest(value=value):
                with self.assertRaises(UnknownModel):
                    parse_numeric_ping(value)
        with self.assertRaises(UnknownModel):
            select_verified_remote_profile("optima270")

    def test_source_selector_ignores_slave_fields_for_optima270(self):
        # Mirrors the exact two-field upstream Optima270 rule. It does NOT
        # establish that other installed hardware variants are remotely safe.
        self.assertIs(
            select_verified_remote_profile(
                DeviceMetadata(2010, 79265, 1, 4294967295, 4294967295)
            ),
            OPTIMA_270,
        )


if __name__ == "__main__":
    unittest.main()
