#!/usr/bin/env python3
"""Read-only local lookup in the source-audited Micro Nabto protocol library.

Examples:
  python scripts/lookup_micro_nabto.py --commands
  python scripts/lookup_micro_nabto.py --models
  python scripts/lookup_micro_nabto.py --model optima270 --setpoints
  python scripts/lookup_micro_nabto.py --model optima270 --rpc 43 --address 24
  python scripts/lookup_micro_nabto.py --model optima270 --key fan_speed
Never imports the Nabto SDK, creates a connection, or transmits a write.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experimental/genvex_remote"))

from register_catalog import (  # noqa: E402
    MICRO_COMMANDS, MODEL_PROFILES, get_model,
    get_model_register, get_model_setpoint,
)


def lookup(argv: list[str] | None = None) -> object:
    cli = argparse.ArgumentParser(description=__doc__)
    group = cli.add_mutually_exclusive_group(required=True)
    group.add_argument("--models", action="store_true")
    group.add_argument("--commands", action="store_true")
    group.add_argument("--datapoints", action="store_true")
    group.add_argument("--setpoints", action="store_true")
    group.add_argument("--inactive", action="store_true")
    group.add_argument("--rpc", type=int, choices=(42, 43, 45))
    group.add_argument("--key")
    cli.add_argument("--model", choices=sorted(MODEL_PROFILES))
    cli.add_argument("--address", type=int)
    cli.add_argument("--object", dest="object_id", type=int, default=0)
    cli.add_argument("--include-inactive", action="store_true")
    args = cli.parse_args(argv)

    if args.models:
        return [
            {"key": item.model_key, "name": item.model_name,
             "identity_hint_unverified": item.identity_hint}
            for item in MODEL_PROFILES.values()
        ]
    if args.commands:
        return [asdict(cmd) for cmd in MICRO_COMMANDS]
    if args.model is None:
        cli.error("--model is required for register/setpoint lookups")
    if args.rpc is not None:
        if args.address is None:
            cli.error("--address is required with --rpc")
        item = get_model_register(
            args.model, args.rpc, args.address, object_id=args.object_id,
            include_inactive=args.include_inactive,
        )
        return {
            "model": args.model,
            "rpc": args.rpc,
            "register": asdict(item),
        }
    if args.address is not None or args.include_inactive:
        cli.error("--address/--include-inactive require --rpc")
    model = get_model(args.model)
    if args.datapoints:
        return [asdict(item) for item in model.rpc45]
    if args.setpoints:
        return [asdict(item) for item in model.setpoints]
    if args.inactive:
        return [asdict(item) for item in model.inactive_setpoints]
    return asdict(get_model_setpoint(args.model, args.key))


def main() -> int:
    try:
        data = lookup()
    except KeyError:
        print("No such catalog entry", file=sys.stderr)
        return 2
    print(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
