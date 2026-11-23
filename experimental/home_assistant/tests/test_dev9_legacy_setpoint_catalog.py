"""Static source-audited Optima 270 Micro Nabto setpoint map.

This test never imports a Nabto client, opens sockets or executes a write.
The catalog is reference data only, not a writable transport API.
"""
from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "docs/references/optima270_micro_nabto_setpoint_catalog.json"
SOURCE_SETPOINTS = {
    "fan_speed": (7, 24, 1, 0, 0, 4),
    "temp_setpoint": (1, 12, 10, 100, 0, 200),
    "bypass_openoffset": (21, 52, 10, 0, 10, 100),
    "bypass_turnoff": (29, 68, 1, 0, 0, 20),
    "bypass_force_speed": (57, 124, 1, 0, 0, 100),
    "bypass_force_temp": (58, 126, 10, 0, 0, 50),
    "reheating": (3, 16, 1, 0, 0, 1),
    "humidity_control": (6, 22, 1, 0, 0, 1),
    "boost_enable": (30, 70, 1, 0, 0, 1),
    "boost_time": (70, 150, 1, 0, 1, 120),
    "filter_days": (100, 210, 1, 0, 0, 65535),
    "filter_reset": (50, 110, 1, 0, 0, 2),
}
EXCLUDED = {
    "bypass_min_on": (59, 128),
    "supply_air_level1": (10, 30),
    "supply_air_level2": (11, 32),
    "supply_air_level3": (12, 34),
    "supply_air_level4": (8, 26),
    "extract_air_level1": (13, 36),
    "extract_air_level2": (14, 38),
    "extract_air_level3": (15, 40),
    "extract_air_level4": (9, 28),
}


class LegacySetpointCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG.read_text(encoding="utf-8"))

    def test_reference_only_no_verified_write_or_enabled_command(self):
        item = self.catalog
        self.assertEqual(item["schema_version"], "genvex_optima270_legacy_setpoints_v1")
        self.assertEqual(
            item["source"]["status"],
            "community_reverse_engineered_not_official_vendor_specification"
        )
        for point in item["setpoints"]:
            self.assertEqual(point["evidence"], (
                "community_source_and_live_remote_rpc42"
                if point["key"] == "fan_speed" else "public_optima270_model_only"
            ))
            self.assertIs(point["remote_write_verified"], False)
            self.assertIs(point["remote_read_verified"], point["key"] == "fan_speed")
            self.assertIs(point["write_enabled"], False)

    def test_all_twelve_active_setpoints_have_exact_source_addresses(self):
        points = {item["key"]: item for item in self.catalog["setpoints"]}
        self.assertEqual(len(points), len(self.catalog["setpoints"]))
        self.assertEqual(set(points), set(SOURCE_SETPOINTS))
        for name, expected in SOURCE_SETPOINTS.items():
            item = points[name]
            with self.subTest(name=name):
                self.assertEqual(
                    tuple(item[key] for key in (
                        "read_address", "write_address", "divider",
                        "offset", "raw_min", "raw_max"
                    )), expected,
                )
                self.assertEqual(item["read_obj"], 0)
                self.assertEqual(item["write_obj"], 0)
                self.assertGreater(item["divider"], 0)
                self.assertLessEqual(item["raw_min"], item["raw_max"])
                self.assertGreater(item["step"], 0)
                if name != "filter_reset":
                    self.assertIs(item["default_read"], True)
                else:
                    self.assertIs(item["default_read"], False)

    def test_nine_comment_only_locked_definitions_not_active(self):
        excluded = {v["key"]: v for v in self.catalog["excluded"]}
        self.assertEqual(set(excluded), set(EXCLUDED))
        for key, addresses in EXCLUDED.items():
            obj = excluded[key]
            self.assertEqual(
                (obj["read_address"], obj["write_address"]), addresses
            )
            self.assertEqual(obj["status"], "commented_out_in_source")
        self.assertEqual(set(excluded) & set(SOURCE_SETPOINTS), set())

    def test_keep_rpc_opcode_separate_from_register_address(self):
        commands = {item["type"]: item for item in self.catalog["commands"]}
        self.assertEqual(commands["SETPOINT_READLIST"]["id"], 42)
        self.assertEqual(commands["SETPOINT_WRITELIST"]["id"], 43)
        self.assertEqual(commands["DATAPOINT_READLIST"]["id"], 45)
        self.assertEqual(commands["SETPOINT_READLIST"]["hex"], "0x2a")
        self.assertEqual(commands["SETPOINT_WRITELIST"]["hex"], "0x2b")
        self.assertEqual(commands["SETPOINT_WRITELIST"]["current_remote_status"],
                         "not_tested_no_transmit")
        self.assertEqual(
            SOURCE_SETPOINTS["fan_speed"][0], 7,
            "Fan level has a dedicated RPC42 read address; it is not raw duty"
        )

    def test_live_rpc42_single_fan_stage_is_verified_not_all_setpoints(self):
        evidence = self.catalog["live_verification"]
        self.assertEqual(evidence["query_id"], 42)
        self.assertEqual(evidence["read_obj"], 0)
        self.assertEqual(evidence["read_address"], 7)
        self.assertEqual(evidence["fan_level"], 2)
        self.assertTrue(evidence["level_zero_confirmed"])
        self.assertTrue(evidence["simultaneous_rpc45_confirmed"])
        self.assertTrue(evidence["level_zero_controller_feedback_zero_verified"])
        self.assertEqual(evidence["synchronized_result"], "PASS")
        samples = evidence["synchronized_level_zero_samples"]
        self.assertEqual(len(samples), 3)
        self.assertEqual([x["window_ms"] for x in samples], [328, 49, 49])
        self.assertEqual(
            [x["start_utc"] for x in samples],
            [
                "2026-11-22T23:49:22.194944+00:00",
                "2026-11-22T23:49:24.522979+00:00",
                "2026-11-22T23:49:26.572568+00:00",
            ],
        )
        for sample in samples:
            for key in (
                "level_before", "level_after", "rpc45_18", "rpc45_19",
                "rpc45_35", "rpc45_36",
            ):
                self.assertEqual(sample[key], 0)
        self.assertFalse(evidence["level_zero_fan_motor_state_verified"])
        self.assertEqual([x["fan_level"] for x in evidence["observations"]], [2, 0])
        for observation in evidence["observations"]:
            self.assertEqual(observation["response_prefix_unknown"], 0)
            self.assertEqual(observation["xml_register_status"], 0)
            self.assertEqual(observation["invoke_status"], 0)
            self.assertEqual(observation["cli_exit_code"], 0)
        self.assertEqual(evidence["response_prefix_unknown"], 0)
        for key in ("sdk_startup_status", "sdk_resources_status",
                    "sdk_session_status", "xml_register_status",
                    "invoke_status", "sdk_close_status",
                    "sdk_shutdown_status", "cli_exit_code"):
            self.assertEqual(evidence[key], 0)
        self.assertFalse(evidence["write_attempted"])
        self.assertFalse(evidence["other_setpoint_addresses_verified"])
        commands = {x["id"]: x for x in self.catalog["commands"]}
        self.assertEqual(
            commands[42]["current_remote_status"],
            "verified_remote_single_fan_level_address_7",
        )
        self.assertEqual(commands[43]["current_remote_status"],
                         "not_tested_no_transmit")

    def test_temperature_setpoint_formula_is_source_only(self):
        temp = next(x for x in self.catalog["setpoints"] if x["key"] == "temp_setpoint")
        self.assertEqual((150 + temp["offset"]) / temp["divider"], 25.0)
        self.assertEqual(int(25.0 * temp["divider"] - temp["offset"]), 150)
        # Only validate source metadata; no packet is assembled or sent.


if __name__ == "__main__":
    unittest.main()
