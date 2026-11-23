#!/usr/bin/env python3
"""Offline contract gate for DEV9 App/HA settings and release versions.

Supervisor config.yaml owns App defaults and option names. app_bootstrap.py
contains a pure-Python runtime projection, and the HA integration maintains
separate authentication/UI configuration. This gate fails on accidental drift
without needing PyYAML, Home Assistant Core, Nabto, credentials or network.
"""
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "genvex-nabto-remote"
HA = ROOT / "experimental/home_assistant/custom_components/genvex_remote"


def _yaml_map(text: str, section: str) -> dict[str, object]:
    match = re.search(
        rf"(?m)^{re.escape(section)}:\n((?:  [a-z0-9_]+: [^\n]*\n)+)", text,
    )
    if match is None:
        raise ValueError(f"Missing or irregular App {section} section")
    values = {}
    for line in match.group(1).splitlines():
        name, raw = line.strip().split(": ", 1)
        if name in values:
            raise ValueError("Duplicate App option")
        if raw == "false":
            value = False
        elif raw == "true":
            value = True
        elif raw == '""':
            value = ""
        elif re.fullmatch(r"[0-9]+", raw):
            value = int(raw)
        else:
            value = raw
        values[name] = value
    return values


def _ha_constants() -> dict[str, str]:
    tree = ast.parse((HA / "const.py").read_text(encoding="utf-8"))
    result = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Constant)
                and type(node.value.value) is str):
            result[node.targets[0].id] = node.value.value
    return result


def check() -> None:
    config = (APP / "config.yaml").read_text(encoding="utf-8")
    defaults = _yaml_map(config, "options")
    schema = _yaml_map(config, "schema")
    sys.path.insert(0, str(APP / "runtime"))
    try:
        import app_bootstrap
    finally:
        sys.path.pop(0)
    if (set(defaults) != set(schema)
            or set(defaults) != set(app_bootstrap.VALID_OPTION_KEYS)):
        raise ValueError("App option keys differ across manifest and bootstrap")
    if not all(defaults[key] == "" for key in app_bootstrap.REQUIRED_OPTION_KEYS):
        raise ValueError("Credential defaults must remain empty")
    if {
        key: defaults[key] for key in app_bootstrap.APP_DEFAULTS
    } != app_bootstrap.APP_DEFAULTS:
        raise ValueError("App optional defaults differ from manifest")
    for key in ("persistent_session", "raw_registers_v3", "fan_level_v4",
                "diagnostic_only"):
        if defaults[key] is not False or schema[key] != "bool":
            raise ValueError(f"Invalid default/boolean schema for {key}")
    if defaults["poll_seconds"] != 60 or schema["poll_seconds"] != "int(60,3600)":
        raise ValueError("Poll interval differs from validated DEV9 limits")
    if schema["ipc_token"] != "password" or schema["unlock_secret"] != "password":
        raise ValueError("Credential schema must remain secret")

    ha_constants = _ha_constants()
    if (ha_constants.get("CONF_RAW_REGISTERS_V3") != "raw_registers_v3"
            or ha_constants.get("CONF_FAN_LEVEL_V4") != "fan_level_v4"
            or ha_constants.get("CONF_PAIR_FROM_APP") != "pair_from_app"):
        raise ValueError("HA options and App mode keys differ")

    spec = importlib.util.spec_from_file_location(
        "dev9_combined_package", ROOT / "scripts/package_dev9_combined.py",
    )
    if spec is None or spec.loader is None:
        raise ValueError("Missing DEV9 package script")
    release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)
    app_match = re.search(r'^version: "([^"\r\n]+)"$', config, re.MULTILINE)
    manifest = json.loads((HA / "manifest.json").read_text(encoding="utf-8"))
    if app_match is None or (
        release.APP_VERSION != app_match.group(1)
        or release.HA_VERSION != manifest["version"]
    ):
        raise ValueError("Release versions drift from manifests")
    if release.REGISTER_ADDRESSES != tuple(
        spec.address for spec in release.CATALOG.RPC45_ALL
    ):
        raise ValueError("Package register inventory differs from catalog")
    if release.FAN_LEVEL_READ != {
        "object": 0, "address": 7, "range": [0, 4],
    }:
        raise ValueError("DEV9 fan-stage contract was changed")


def main() -> int:
    try:
        check()
    except (OSError, ValueError, KeyError, ImportError, SyntaxError) as exc:
        # Source-only contract errors cannot include runtime credentials.
        print(f"REMOTE_CONTRACTS: FAIL {type(exc).__name__}: {exc}")
        return 1
    print("REMOTE_CONTRACTS: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
