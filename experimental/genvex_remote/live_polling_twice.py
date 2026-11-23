#!/usr/bin/env python3
"""Temporary two-poll real RPC45 diagnostic, no listener and no persistence.

Run only inside disposable SDK runtime with a copied encrypted profile.
Reads identity and passphrase from stdin. Does not print measurements or secrets.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sdk_snapshot_adapter import SDKSnapshotAdapter
from snapshot_state import SnapshotState
from polling_service import PollingService


async def main() -> None:
    device = sys.stdin.readline().strip()
    identity = sys.stdin.readline().strip()
    secret = sys.stdin.readline().rstrip("\r\n")
    if not device or not identity or not secret:
        raise ValueError("Missing diagnostic input")
    adapter = SDKSnapshotAdapter(
        device_id=device,
        identity=identity,
        unlock_secret=secret,
        profile_dir="/tmp/genvex-profile",
        probe_file="/tmp/genvex-live/probe_remote_snapshot.py",
        timeout_seconds=85,
    )
    state = SnapshotState(adapter)
    successes = []
    complete = asyncio.Event()

    async def report(ok: bool) -> None:
        if ok:
            snapshot = state.current()
            if snapshot is not None and len(snapshot["values"]) == 5:
                successes.append(snapshot["timestamp_utc"])
                print(f"PASS: authenticated read-only RPC45 poll {len(successes)}/2 validated", flush=True)
                if len(successes) == 2:
                    complete.set()
        else:
            print("Read-only poll failed; values unavailable", flush=True)

    service = PollingService(state, interval_seconds=5, on_result=report)
    try:
        await service.start()
        await asyncio.wait_for(complete.wait(), timeout=210)
    finally:
        await service.stop()
    if state.current() is not None:
        raise RuntimeError("Polling stop failed to invalidate snapshot")
    if len(successes) != 2 or successes[0] == successes[1]:
        raise RuntimeError("Did not obtain two distinct fresh snapshots")
    print("PASS: two serial live polls, distinct timestamps and fail-closed stop", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        print("FAIL: live polling diagnostic incomplete (details suppressed)", file=sys.stderr)
        sys.exit(1)
