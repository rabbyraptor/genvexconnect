#!/usr/bin/env python3
"""Generate/check HA per-user sensor translations from the canonical RPC catalog.

Only entity.sensor metadata is generated; config/options translations are
preserved. No Home Assistant Core, SDK, credentials or network access needed.
Use --sync after adding a register, and --check in offline CI.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experimental/genvex_remote"
HA = ROOT / "experimental/home_assistant/custom_components/genvex_remote"
_source_path = str(SOURCE)
sys.path.insert(0, _source_path)
try:
    from register_catalog import (
        MODEL_PROFILES, RPC45_DEFAULT_ICONS, rpc45_english_name,
    )
finally:
    sys.path.remove(_source_path)

EN = HA / "strings.json"
DA = HA / "translations/da.json"
EN_TRANSLATION = HA / "translations/en.json"

# Existing entity translation keys stay stable across upgrades. The generic
# English originals are retained where they already exist.
BASE_KEYS = (
    "supply_air", "outdoor_air", "exhaust_air", "extract_air",
    "humidity", "data_age", "fan_level",
)


def _read(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if type(payload) is not dict or type(payload.get("entity")) is not dict:
        raise ValueError("Invalid integration translation structure")
    sensors = payload["entity"].get("sensor")
    if type(sensors) is not dict:
        raise ValueError("Missing sensor translations")
    return payload


def generated() -> tuple[dict, dict]:
    english = _read(EN)
    danish = _read(DA)
    en_sensors = english["entity"]["sensor"]
    da_sensors = danish["entity"]["sensor"]
    if any(key not in en_sensors or key not in da_sensors for key in BASE_KEYS):
        raise ValueError("Existing HA entity translation was removed")

    en_names = {key: en_sensors[key] for key in BASE_KEYS}
    da_names = {key: da_sensors[key] for key in BASE_KEYS}
    seen = set(BASE_KEYS)
    for model in MODEL_PROFILES.values():
        # DEV9's existing Optima 270 keys must never acquire a model prefix.
        # Future model-specific entities can use their own prefixed keys.
        prefix = "" if model.model_key == "optima270" else model.model_key + "_"
        for spec in model.rpc45:
            key = prefix + "raw_" + spec.key
            if key in seen or spec.key not in RPC45_DEFAULT_ICONS:
                raise ValueError(f"Unresolved translation/icon metadata: {key}")
            seen.add(key)
            en_name = f"RPC45 raw {spec.address} – {rpc45_english_name(spec)}"
            da_name = f"RPC45 råværdi {spec.address} – {spec.label}"
            en_names[key] = {"name": en_name}
            da_names[key] = {"name": da_name}
    english["entity"]["sensor"] = en_names
    danish["entity"]["sensor"] = da_names
    return english, danish


def check_or_sync(*, sync: bool) -> bool:
    english, danish = generated()
    expected = (
        (EN, english),
        (DA, danish),
        (EN_TRANSLATION, english),
    )
    drift = []
    for path, wanted in expected:
        if path.is_file():
            existing = _read(path)
            if existing == wanted:
                continue
        if sync:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(wanted, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        else:
            drift.append(path.relative_to(ROOT).as_posix())
    if drift:
        print("HA_SENSOR_TRANSLATIONS: DRIFT " + ", ".join(drift))
        print("Run: python scripts/sync_remote_entity_localizations.py --sync")
        return False
    print("HA_SENSOR_TRANSLATIONS: SYNCED" if sync
          else "HA_SENSOR_TRANSLATIONS: PASS")
    return True


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    flags = cli.add_mutually_exclusive_group()
    flags.add_argument("--sync", action="store_true")
    flags.add_argument("--check", action="store_true")
    args = cli.parse_args()
    try:
        return 0 if check_or_sync(sync=args.sync) else 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("HA_SENSOR_TRANSLATIONS: FAIL " + type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
