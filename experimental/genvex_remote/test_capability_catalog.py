"""2A offline tests: capability metadata and snapshot v1 compatibility.

Run: python3 -m unittest discover -s experimental/genvex_remote
Never imports the Nabto SDK or Home Assistant Core; never contacts a gateway.
"""
import unittest

from capability_catalog import CatalogError, ControllerProfile, Reading, OPTIMA_270, get_profile
from sensor_model import SENSORS, decode_readings


class CapabilityCatalogTests(unittest.TestCase):
    def test_verified_rpc45_address_order_matches_existing_runtime(self):
        self.assertEqual(OPTIMA_270.read_rpc_id, 45)
        self.assertEqual(OPTIMA_270.read_addresses,
                         ((0, 20), (0, 21), (0, 22), (0, 23), (0, 26)))
        self.assertEqual([(s.key, s.address) for s in OPTIMA_270.readings],
                         [(s.key, s.address) for s in SENSORS])
        self.assertEqual(OPTIMA_270.capability_enumeration, "unverified")
        self.assertEqual({s.evidence for s in OPTIMA_270.readings},
                         {"remote_rpc45_verified"})

    def test_current_five_sensor_schema_is_unchanged(self):
        for raw in ([365, 301, 315, 376, 66],
                    [367, 295, 313, 377, 65],
                    [-32768, 0, 32767, 365, 100]):
            with self.subTest(raw=raw):
                self.assertEqual(OPTIMA_270.decode_batch(raw), decode_readings(raw))
        self.assertEqual(set(OPTIMA_270.decode_batch([365, 301, 315, 376, 66])),
                         {"supply_air", "outdoor_air", "exhaust_air", "extract_air", "humidity"})

    def test_atomic_invalid_batch_is_rejected(self):
        for raw in (
            [], [365], [365, 301, 315, 376, 66, 1],
            [365, 301, 315, None, 66], [365, 301, 315, True, 66],
            [365, 301, 315, 32768, 66], [365, 301, 315, 1.1, 66],
            [365, 301, 315, "376", 66],
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(CatalogError):
                    OPTIMA_270.decode_batch(raw)

    def test_model_selection_must_be_explicit(self):
        self.assertIs(get_profile("optima270"), OPTIMA_270)
        for bad in ("", "cts602", "optima271", None):
            with self.subTest(model=bad):
                with self.assertRaises(CatalogError):
                    get_profile(bad)

    def test_reject_duplicate_keys_and_addresses(self):
        original = OPTIMA_270.readings[0]
        another = OPTIMA_270.readings[1]
        with self.assertRaises(CatalogError):
            ControllerProfile("bad", "Vendor", "Device", 45, (original, original))
        dup_addr = Reading("other", "Other", 0, original.address,
                           "number", "sensor", "temperature")
        with self.assertRaises(CatalogError):
            ControllerProfile("bad", "Vendor", "Device", 45, (original, dup_addr))
        with self.assertRaises(CatalogError):
            ControllerProfile("bad", "Vendor", "Device", 45, (another, another))

    def test_boolean_is_a_future_synthetic_type_not_automatically_discovered(self):
        binary = Reading("fake_bypass", "Fake bypass", 0, 999,
                         "boolean", "binary_sensor", None)
        self.assertIs(binary.decode(0), False)
        self.assertIs(binary.decode(1), True)
        with self.assertRaises(CatalogError):
            binary.decode(2)
        with self.assertRaises(CatalogError):
            Reading("invalid", "Invalid", 0, 999, "boolean", "sensor", None)
        self.assertNotIn(binary, OPTIMA_270.readings)

    def test_enum_is_an_explicit_future_type(self):
        spec = Reading("fake_mode", "Fake mode", 0, 998, "enum", "sensor",
                       "enum", enum_options=((0, "idle"), (1, "running")))
        self.assertEqual(spec.decode(1), "running")
        with self.assertRaises(CatalogError):
            spec.decode(9)
        with self.assertRaises(CatalogError):
            Reading("fake_mode", "Fake mode", 0, 998, "enum", "sensor",
                    "enum", enum_options=((0, "idle"), (0, "running")))
        self.assertNotIn(spec, OPTIMA_270.readings)

    def test_invalid_metadata_rejected_before_use(self):
        cases = [
            {"key": "UPPER"},
            {"address": -1},
            {"object_id": -1},
            {"scale_divisor": 0},
            {"scale_divisor": True},
            {"kind": "string"},
            {"ha_platform": "switch"},
            {"evidence": ""},
        ]
        base = dict(key="dummy", label="Dummy", object_id=0, address=77,
                    kind="number", ha_platform="sensor", device_class="temperature")
        for changes in cases:
            with self.subTest(changes=changes):
                with self.assertRaises(CatalogError):
                    Reading(**(base | changes))


if __name__ == "__main__":
    unittest.main()
