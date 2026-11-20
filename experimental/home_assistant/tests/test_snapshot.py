"""Offline tests for the HA component snapshot parser; no HA runtime needed."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import importlib.util
import sys
import types
import unittest

# Load import-free component modules without executing its HA-dependent
# __init__.py, so the test works in a plain Python CI environment.
HERE = Path(__file__).resolve().parents[1] / "custom_components" / "genvex_remote"
pkg = types.ModuleType("dev_remote")
pkg.__path__ = [str(HERE)]
sys.modules[pkg.__name__] = pkg
for name in ("const", "snapshot", "runtime_client"):
    spec = importlib.util.spec_from_file_location(f"dev_remote.{name}", HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

from dev_remote.const import SENSORS, valid_device_id
from dev_remote.snapshot import InvalidSnapshot, validate_snapshot
from dev_remote.runtime_client import UnconfiguredReader, RuntimeUnavailable


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.data = {
            "schema_version": 1, "device_id": "123456789012",
            "timestamp_utc": self.now.isoformat(), "health": "ok",
            "values": {"supply_air": 6.5, "outdoor_air": 0.1, "exhaust_air": 1.5,
                       "extract_air": 7.6, "humidity": 66.0},
        }

    def check(self):
        return validate_snapshot(self.data, expected_device_id="123456789012", now=self.now)

    def test_valid(self):
        self.assertEqual(self.check()["humidity"], 66.0)

    def test_addresses_and_stable_keys(self):
        self.assertEqual([(s.key, s.address) for s in SENSORS],
                         [("supply_air", 20), ("outdoor_air", 21),
                          ("exhaust_air", 22), ("extract_air", 23), ("humidity", 26)])

    def test_bad_id(self):
        for value in ("123", "１２３４５６７８９０１２", "12345678901x"):
            self.assertFalse(valid_device_id(value))
        self.assertTrue(valid_device_id("123456789012"))

    def test_stale(self):
        self.data["timestamp_utc"] = (self.now - timedelta(seconds=190)).isoformat()
        with self.assertRaises(InvalidSnapshot):
            self.check()

    def test_future(self):
        self.data["timestamp_utc"] = (self.now + timedelta(seconds=60)).isoformat()
        with self.assertRaises(InvalidSnapshot):
            self.check()

    def test_mismatched_device(self):
        self.data["device_id"] = "000000000000"
        with self.assertRaises(InvalidSnapshot):
            self.check()

    def test_missing_field(self):
        del self.data["values"]["humidity"]
        with self.assertRaises(InvalidSnapshot):
            self.check()

    def test_invalid_readings(self):
        for bad in (True, "1.0", float("nan"), float("inf")):
            self.data["values"]["humidity"] = bad
            with self.assertRaises(InvalidSnapshot):
                self.check()

    def test_unconfigured_reader_never_returns_sensor_values(self):
        import asyncio
        async def run():
            with self.assertRaises(RuntimeUnavailable):
                await UnconfiguredReader().async_fetch_snapshot("123456789012")
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
