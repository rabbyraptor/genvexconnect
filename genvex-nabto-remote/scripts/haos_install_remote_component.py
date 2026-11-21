#!/usr/bin/env python3
"""Install or explicitly upgrade the isolated genvex_remote HA component.

The default is a dry-run. A reviewed upgrade preserves a sibling backup of
the prior component source and requires a later Home Assistant Core reload.
No HA registries, LAN integration, App options or credentials are changed.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile

FILES = (
    "__init__.py", "config_flow.py", "const.py", "coordinator.py",
    "manifest.json", "runtime_client.py", "sensor.py", "snapshot.py",
    "strings.json", "translations/en.json", "translations/da.json",
)
DOMAIN = "genvex_remote"


def validate_sources(source: Path) -> None:
    if source.is_symlink() or not source.is_dir():
        raise ValueError("Invalid source directory")
    for name in FILES:
        path = source / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 60000:
            raise ValueError("Missing or unsafe source")
        if path.suffix == ".py":
            compile(path.read_bytes(), str(path), "exec")
    # HA Core does not substitute strings.json for a missing en.json.
    # Verify both shipped language files have matching sensor keys.
    source_strings = json.loads((source / "strings.json").read_text(encoding="utf-8"))
    english = json.loads((source / "translations/en.json").read_text(encoding="utf-8"))
    danish = json.loads((source / "translations/da.json").read_text(encoding="utf-8"))
    names = source_strings["entity"]["sensor"]
    if english != source_strings or set(names) != set(danish["entity"]["sensor"]):
        raise ValueError("Incomplete entity translations")
    if set(names) != {"supply_air", "outdoor_air", "exhaust_air", "extract_air", "humidity"}:
        raise ValueError("Unexpected sensor translation keys")
    for lang in (english, danish):
        if not all(isinstance(lang["entity"]["sensor"][key].get("name"), str)
                   and lang["entity"]["sensor"][key]["name"] for key in names):
            raise ValueError("Missing sensor translation name")
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("domain") != DOMAIN or manifest.get("config_flow") is not True:
        raise ValueError("Unexpected integration manifest")


def install(source: Path, config: Path, *, apply: bool) -> str:
    validate_sources(source)
    if config.is_symlink() or not config.is_dir():
        raise ValueError("Invalid Home Assistant configuration directory")
    parent = config / "custom_components"
    if parent.is_symlink():
        raise ValueError("Unsafe custom_components directory")
    target = parent / DOMAIN
    if target.exists() or target.is_symlink():
        raise ValueError("Remote integration already exists; refusing overwrite")
    if not apply:
        return "PASS: REMOTE_COMPONENT_PREFLIGHT_ONLY"
    parent.mkdir(mode=0o755, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".genvex_remote-stage-", dir=parent))
    try:
        for name in FILES:
            destination = stage / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, destination, follow_symlinks=False)
            os.chmod(destination, 0o644)
        validate_sources(stage)
        # Atomic publish; no existing installation is replaced.
        stage.rename(target)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return "PASS: REMOTE_COMPONENT_INSTALLED_RESTART_REQUIRED"



def upgrade(source: Path, config: Path, *, apply: bool) -> str:
    """Stage replacement source, keeping one explicit rollback directory.

    Only the integration's own folder is swapped. A single directory rename
    cannot replace a nonempty existing directory; in the exceptional failure
    after moving it to the backup, restore it before returning an error.
    """
    validate_sources(source)
    if config.is_symlink() or not config.is_dir():
        raise ValueError("Invalid Home Assistant configuration directory")
    parent = config / "custom_components"
    target = parent / DOMAIN
    backup = parent / ".genvex_remote-upgrade-backup"
    if parent.is_symlink() or target.is_symlink() or not target.is_dir():
        raise ValueError("Expected installed remote component")
    if backup.exists() or backup.is_symlink():
        raise ValueError("Prior upgrade backup exists; review it first")
    if source.resolve() == target.resolve() or target.resolve() in source.resolve().parents:
        raise ValueError("Source must be independent of target")
    manifest_path = target / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("Unsafe installed manifest")
    installed = json.loads(manifest_path.read_text(encoding="utf-8"))
    if installed.get("domain") != DOMAIN:
        raise ValueError("Installed integration mismatch")
    for name in ("__init__.py", "sensor.py", "config_flow.py", "coordinator.py"):
        path = target / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Unexpected installed integration source")
    if not apply:
        return "PASS: REMOTE_COMPONENT_UPGRADE_PREFLIGHT_ONLY"

    stage = Path(tempfile.mkdtemp(prefix=".genvex_remote-upgrade-stage-", dir=parent))
    try:
        for name in FILES:
            destination = stage / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, destination, follow_symlinks=False)
            os.chmod(destination, 0o644)
        validate_sources(stage)
        target.rename(backup)
        try:
            stage.rename(target)
        except OSError:
            backup.rename(target)
            raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return "PASS: REMOTE_COMPONENT_UPGRADED_BACKUP_RETAINED_RESTART_REQUIRED"

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("/mnt/data/supervisor/homeassistant"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--install", action="store_true")
    mode.add_argument("--upgrade", action="store_true")
    mode.add_argument("--upgrade-preflight", action="store_true")
    args = parser.parse_args()
    try:
        if os.geteuid() != 0:
            raise ValueError("Root required")
        if args.upgrade or args.upgrade_preflight:
            result = upgrade(args.source, args.config, apply=args.upgrade)
        else:
            result = install(args.source, args.config, apply=args.install)
        print(result, flush=True)
        return 0
    except (OSError, ValueError, SyntaxError, json.JSONDecodeError):
        print("BLOCKED: REMOTE_COMPONENT_INSTALL_PRECONDITION", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
