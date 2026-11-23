"""Offline catalog contract: all known legacy Micro opcodes and setpoints.

Cross-check the source-audited 2026-11-23 reference artifact against the
single deployable code library. No SDK, network or write packet is invoked.
"""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from register_catalog import (
    MICRO_COMMANDS, MICRO_COMMAND_BY_ID, MODEL_PROFILES,
    OPTIMA270_SETPOINTS, OPTIMA270_INACTIVE_SETPOINTS,
    RPC42_FAN_LEVEL, RPC45_ALL,
    get_micro_command, get_model, get_model_register, get_model_setpoint,
)

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "docs/references/optima270_micro_nabto_setpoint_catalog.json"


class MicroProtocolCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = json.loads(REFERENCE.read_text(encoding="utf-8"))

    def test_five_source_documented_commands_have_distinct_opcodes(self):
        self.assertEqual(
            {item.opcode: item.name for item in MICRO_COMMANDS},
            {2: "KEEP_ALIVE", 17: "PING", 42: "SETPOINT_READLIST",
             43: "SETPOINT_WRITELIST", 45: "DATAPOINT_READLIST"},
        )
        self.assertEqual(set(MICRO_COMMAND_BY_ID), {
            item["id"] for item in self.reference["commands"]
        })
        for item in self.reference["commands"]:
            command = get_micro_command(item["id"])
            self.assertEqual(command.name, item["type"])
            self.assertEqual(command, get_micro_command(item["type"]))
            self.assertEqual(item["hex"], f"0x{command.opcode:02x}")
        self.assertFalse(get_micro_command(43).transmit_enabled)
        self.assertFalse(get_micro_command(43).remote_verified)
        self.assertTrue(get_micro_command(42).remote_verified)
        self.assertTrue(get_micro_command(45).remote_verified)
        with self.assertRaises(KeyError):
            get_micro_command(999)

    def test_every_setpoint_pair_and_source_conversion_is_present(self):
        model = get_model("optima270")
        self.assertEqual(set(MODEL_PROFILES), {"optima270"})
        expected = self.reference["setpoints"]
        self.assertEqual(len(model.setpoints), len(expected))
        self.assertEqual(len(OPTIMA270_SETPOINTS), 12)
        self.assertEqual(sum(s.default_read for s in model.setpoints), 11)
        for reference in expected:
            with self.subTest(key=reference["key"]):
                spec = get_model_setpoint("optima270", reference["key"])
                for field, attr in (
                    ("label", "label"), ("read_obj", "read_object"),
                    ("read_address", "read_address"), ("write_obj", "write_object"),
                    ("write_address", "write_address"), ("divider", "divisor"),
                    ("offset", "offset"), ("raw_min", "raw_min"),
                    ("raw_max", "raw_max"), ("step", "step"),
                    ("default_read", "default_read"), ("evidence", "evidence"),
                    ("remote_read_verified", "remote_read_verified"),
                    ("remote_write_verified", "remote_write_verified"),
                    ("write_enabled", "write_enabled"),
                ):
                    self.assertEqual(
                        getattr(spec, attr), reference[field], field,
                    )
                self.assertIs(
                    get_model_register("optima270", 42, spec.read_address),
                    spec,
                )
                self.assertIs(
                    get_model_register("optima270", 43, spec.write_address),
                    spec,
                )
                self.assertEqual(
                    spec.display_value(spec.raw_min),
                    (spec.raw_min + spec.offset) / spec.divisor,
                )
                self.assertFalse(spec.remote_write_verified)
                self.assertFalse(spec.write_enabled)
                with self.assertRaises(ValueError):
                    spec.display_value(spec.raw_min - 1)

    def test_source_excluded_setpoints_stay_inactive(self):
        self.assertEqual(len(OPTIMA270_INACTIVE_SETPOINTS), 9)
        for reference in self.reference["excluded"]:
            with self.subTest(key=reference["key"]):
                entry = next(
                    x for x in OPTIMA270_INACTIVE_SETPOINTS
                    if x.key == reference["key"]
                )
                self.assertEqual(entry.read_address, reference["read_address"])
                self.assertEqual(entry.write_address, reference["write_address"])
                self.assertEqual(entry.reason, reference["reason"])
                with self.assertRaises(KeyError):
                    get_model_register("optima270", 42, entry.read_address)
                self.assertIs(
                    get_model_register(
                        "optima270", 43, entry.write_address,
                        include_inactive=True,
                    ), entry,
                )
                with self.assertRaises(KeyError):
                    get_model_setpoint("optima270", entry.key)

    def test_namespaces_and_model_selection_do_not_collide(self):
        self.assertEqual(RPC42_FAN_LEVEL.address, 7)
        self.assertEqual(get_model_register(
            "optima270", 42, 7,
        ).key, "fan_speed")
        self.assertEqual(get_model_register(
            "optima270", 43, 24,
        ).key, "fan_speed")
        self.assertEqual(get_model_register(
            "optima270", 45, 24,
        ).key, "frost_protection_temp")
        self.assertEqual(get_model_register(
            "optima270", 45, 21,
        ).key, "outdoor_air")
        self.assertEqual(get_model_register(
            "optima270", 42, 21,
        ).key, "bypass_openoffset")
        self.assertEqual(len(RPC45_ALL), 17)
        for args in (
            ("other", 42, 7), ("optima270", 43, 7),
            ("optima270", 45, 99), ("optima270", 42, 7),
        ):
            if args == ("optima270", 42, 7):
                with self.assertRaises(KeyError):
                    get_model_register(*args, object_id=1)
            else:
                with self.assertRaises(KeyError):
                    get_model_register(*args)
        with self.assertRaises(KeyError):
            get_model("unknown")

    def test_write_operations_are_metadata_only(self):
        # Source-only LAN packet layout != proven remote Nabto SDK XML schema.
        command = get_micro_command("SETPOINT_WRITELIST")
        self.assertIn("SDK write schema unknown", command.response)
        for model in MODEL_PROFILES.values():
            for item in model.setpoints:
                self.assertFalse(item.write_enabled)
                self.assertFalse(item.remote_write_verified)


if __name__ == "__main__":
    unittest.main()
