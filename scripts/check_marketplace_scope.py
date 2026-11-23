#!/usr/bin/env python3
"""Offline Home Assistant Marketplace layout guard.

The root Marketplace metadata describes the existing LAN integration only.
The experimental Remote App and the separate Remote HA component are not
installed or published by that metadata. hacs.json and hacs/action remain
historical API names in the built-in Marketplace (HA Core 2026.11+).

This gate does not inspect or change GitHub topics/Issues repository settings.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(root: Path = ROOT) -> None:
    root_components = root / "custom_components"
    names = {p.name for p in root_components.iterdir() if p.is_dir()}
    if names != {"genvex_connect"}:
        raise ValueError("Root Marketplace must expose only the existing LAN integration")

    metadata = json.loads((root / "hacs.json").read_text(encoding="utf-8"))
    if (type(metadata) is not dict
            or metadata.get("name") != "Genvex Connect"
            or metadata.get("filename") != "genvex_connect.zip"):
        raise ValueError("Marketplace root package ownership changed")

    lan_manifest = json.loads(
        (root_components / "genvex_connect/manifest.json").read_text(encoding="utf-8")
    )
    remote_manifest = json.loads((
        root / "experimental/home_assistant/custom_components"
        / "genvex_remote/manifest.json"
    ).read_text(encoding="utf-8"))
    if (lan_manifest.get("domain") != "genvex_connect"
            or remote_manifest.get("domain") != "genvex_remote"
            or not (root / "genvex-nabto-remote/config.yaml").is_file()):
        raise ValueError("LAN/Remote/App separation changed")


def main() -> int:
    try:
        check()
    except (OSError, ValueError, KeyError, TypeError):
        print("MARKETPLACE_SCOPE: FAIL")
        return 1
    print("MARKETPLACE_SCOPE: PASS (LAN integration only; Remote separate)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
