"""Offline unit tests: python3 -m unittest discover -s experimental/genvex_remote."""
import unittest
from sensor_model import SENSORS, InvalidBatch, decode_readings, remote_hostname


class TestRemoteSensorModel(unittest.TestCase):
    def test_verified_haos_batch(self):
        actual = decode_readings([365, 301, 315, 376, 66])
        self.assertEqual(actual, {
            "supply_air": 6.5, "outdoor_air": 0.1,
            "exhaust_air": 1.5, "extract_air": 7.6, "humidity": 66.0,
        })

    def test_sensor_addresses_are_unique(self):
        self.assertEqual([s.address for s in SENSORS], [20, 21, 22, 23, 26])
        self.assertEqual(len({s.key for s in SENSORS}), 5)

    def test_hostname_from_device_id(self):
        self.assertEqual(remote_hostname("123456789012"), "123456789012.remote.lscontrol.dk")
        for bad in ("", "123", "12345678901x", "１２３４５６７８９０１２"):
            with self.subTest(device_id=bad):
                with self.assertRaises(ValueError):
                    remote_hostname(bad)

    def test_rejects_partial_or_bad_batches(self):
        for bad in ([365], [365, 301, 315, 376, 66, 1],
                    [365, 301, 315, "376", 66],
                    [365, 301, 315, True, 66],
                    [365, 301, 315, 376, 32768]):
            with self.subTest(values=bad):
                with self.assertRaises(InvalidBatch):
                    decode_readings(bad)


if __name__ == "__main__":
    unittest.main()
