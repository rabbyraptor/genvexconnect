#!/usr/bin/env python3
"""Single source-only gate for Remote App/HA release candidates.

--check performs deterministic offline source, parity and localization checks.
--package additionally builds and verifies the DEV9 combined archive/SHA256.
Neither mode talks to HAOS, a gateway, Nabto SDK or Docker.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CHECKS = (
    ("repository_links", ("scripts/check_repository_links.py",)),
    ("marketplace_scope", ("scripts/check_marketplace_scope.py",)),
    ("runtime_parity", ("scripts/check_remote_runtime_parity.py", "--check")),
    ("option_contracts", ("scripts/check_remote_contracts.py",)),
    ("entity_localizations", ("scripts/sync_remote_entity_localizations.py", "--check")),
)


def run_check(name: str, arguments: tuple[str, ...]) -> None:
    proc = subprocess.run(
        [sys.executable, *arguments],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=45,
        check=False,
        text=True,
    )
    if proc.returncode != 0:
        # The subordinate checks only process source files. Keep errors
        # concise; never include Home Assistant options or runtime secrets.
        print(f"REMOTE_RELEASE_GATE: FAIL {name} ({proc.returncode})")
        raise RuntimeError(f"Source gate failed: {name}")
    print(f"REMOTE_RELEASE_GATE: PASS {name}")


def validate_sources() -> None:
    for name, cmd in CHECKS:
        run_check(name, cmd)


def build_combined() -> tuple[str, str]:
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from package_dev9_combined import build, verify, SUMS
    finally:
        sys.path.remove(str(ROOT / "scripts"))
    archive, digest, count = build()
    verified = verify(archive, digest)
    actual_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual_digest != digest or SUMS.read_text(encoding="ascii") != (
        f"{digest}  {archive.name}\n"
    ):
        raise RuntimeError("Combined archive SHA256 does not match manifest")
    if count != len(verified["files"]) + 1:
        raise RuntimeError("Combined package has inconsistent member count")
    print("DEV9_COMBINED_PACKAGE: PASS")
    print(f"REMOTE_RELEASE_GATE: PASS combined_archive ({count} members)")
    return str(archive), digest


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    run = cli.add_mutually_exclusive_group(required=True)
    run.add_argument("--check", action="store_true")
    run.add_argument("--package", action="store_true")
    args = cli.parse_args()
    try:
        validate_sources()
        if args.package:
            build_combined()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, KeyError):
        return 1
    print("REMOTE_RELEASE_GATE: SUCCESS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
