#!/usr/bin/env python3
"""Check or explicitly synchronize shared Remote runtime sources.

The experimental/genvex_remote versions are canonical for modules bundled in
both the experimental package and Supervisor App. App-only bootstrap, profile
import and x86-64 worker files are intentionally not copied or modified.
No HAOS access, SDK invocation, credentials, network or deployment is involved.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experimental/genvex_remote"
BUNDLED = ROOT / "genvex-nabto-remote/runtime"
APP_ONLY = frozenset({
    "app_bootstrap.py",
    "profile_provision.py",
    "offline_ipc_network_smoke.py",
    "diagnostic_http_server.py",
    "persistent_rpc45_worker.py",
})


def shared_files(source: Path = SOURCE, bundled: Path = BUNDLED) -> list[tuple[Path, Path]]:
    """Only files already selected for App packaging participate in sync."""
    result = []
    for candidate in sorted(bundled.glob("*.py")):
        if candidate.name in APP_ONLY:
            continue
        original = source / candidate.name
        if (candidate.is_symlink() or original.is_symlink()
                or not candidate.is_file() or not original.is_file()):
            raise ValueError(f"Missing or unsafe canonical runtime: {candidate.name}")
        result.append((original, candidate))
    if not result:
        raise ValueError("No shared bundled runtime modules")
    return result


def check(source: Path = SOURCE, bundled: Path = BUNDLED) -> list[str]:
    """Report drift by filename only, never print source contents."""
    return [target.name for original, target in shared_files(source, bundled)
            if original.read_bytes() != target.read_bytes()]


def sync(source: Path = SOURCE, bundled: Path = BUNDLED) -> list[str]:
    """Explicit source-controlled regeneration of the bundled copies."""
    changed = []
    for original, target in shared_files(source, bundled):
        if original.read_bytes() != target.read_bytes():
            shutil.copyfile(original, target)
            changed.append(target.name)
    return changed


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    operation = cli.add_mutually_exclusive_group()
    operation.add_argument("--check", action="store_true", help="fail if any shared file differs (default)")
    operation.add_argument("--sync", action="store_true", help="copy canonical files into App runtime")
    args = cli.parse_args()
    try:
        if args.sync:
            changed = sync()
            print("SYNCED:", ", ".join(changed) if changed else "none")
            return 0
        drift = check()
    except (ValueError, OSError) as exc:
        print("RUNTIME_PARITY: ERROR:", type(exc).__name__)
        return 2
    if drift:
        print("RUNTIME_PARITY: DRIFT:", ", ".join(drift))
        print("Run: python scripts/check_remote_runtime_parity.py --sync")
        return 1
    print("RUNTIME_PARITY: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
