#!/usr/bin/env python3
"""Opt-in live smoke for persistent adapter inside an already provisioned App.

Must be staged alongside persistent_sdk_adapter.py and
persistent_rpc45_worker.py in a temporary container directory. Six serial
read-only RPC45 calls; never modifies the running polling service.
No credential, device ID or native SDK text is printed.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
import time

APP_RUNTIME = Path("/opt/genvex-remote/runtime")
if str(APP_RUNTIME) not in sys.path:
    sys.path.append(str(APP_RUNTIME))
from persistent_sdk_adapter import PersistentSDKSnapshotAdapter
from sdk_snapshot_adapter import SDKSnapshotError
from snapshot_contract import parse_snapshot

ATTEMPTS = 6
INTERVAL = 60
KEYS = {"supply_air", "outdoor_air", "exhaust_air", "extract_air", "humidity"}


def read_options(path: Path = Path("/data/options.json")) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 8192:
        raise ValueError("Invalid options")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Invalid options")
    if (type(data.get("device_id")) is not str
            or len(data["device_id"]) != 12
            or not data["device_id"].isascii()
            or not data["device_id"].isdecimal()
            or any(type(data.get(k)) is not str or not data[k]
                   for k in ("identity", "unlock_secret"))):
        raise ValueError("Missing live identity")
    return data


async def run_trial(adapter: PersistentSDKSnapshotAdapter, *, sleep=asyncio.sleep) -> dict:
    success = 0
    statuses = []
    workers = set()
    previous_worker = None
    failure_worker = None
    recovered_in_same_session = False
    print("===== DEV3 PERSISTENT ADAPTER LIVE GATE =====", flush=True)
    try:
        for index in range(ATTEMPTS):
            if index:
                await sleep(INTERVAL)
            previous_worker = adapter._proc.pid if adapter._proc else None
            begun = time.monotonic()
            status = None
            try:
                payload = await adapter.poll_once()
                values = parse_snapshot(payload, expected_device_id=adapter.device_id)
                if set(values) != KEYS:
                    raise ValueError("Incomplete values")
                success += 1
                status = 0
            except SDKSnapshotError as exc:
                status = exc.rpc_status if exc.code == "SDK_RPC45_FAILED" else exc.code
            except Exception:
                status = "SNAPSHOT_INVALID"
            elapsed = round((time.monotonic() - begun) * 1000)
            pid = adapter._proc.pid if adapter._proc else None
            if pid is not None:
                workers.add(pid)
            if status == 0 and failure_worker is not None and failure_worker == pid:
                recovered_in_same_session = True
            if status != 0 and pid is not None:
                failure_worker = pid
            elif status == 0:
                failure_worker = None
            statuses.append(status)
            reuse = (previous_worker is not None and pid == previous_worker)
            print(
                f"RPC45_{index+1}: status={status} "
                f"values={5 if status == 0 else 0} elapsed_ms={elapsed} "
                f"worker_reused={reuse} worker_retained={pid is not None}",
                flush=True,
            )
        print("SUCCESSFUL_READS:", str(success) + "/" + str(ATTEMPTS))
        print("WORKERS_OBSERVED:", len(workers))
        print("RPC_FAILURES:", ATTEMPTS - success)
        print("RECOVERED_AFTER_ERROR_IN_SAME_WORKER:", recovered_in_same_session)
        return {
            "success": success, "statuses": statuses,
            "workers": len(workers),
            "recovered": recovered_in_same_session,
        }
    finally:
        await adapter.aclose()
        print("WORKER_CLOSED:", adapter._proc is None, flush=True)


def main() -> int:
    if sys.argv[1:] != ["--run-live"]:
        return 2
    try:
        data = read_options()
        worker_path = Path(__file__).with_name("persistent_rpc45_worker.py")
        if not worker_path.is_file() or worker_path.is_symlink():
            raise ValueError("Worker file missing")
        adapter = PersistentSDKSnapshotAdapter(
            device_id=data["device_id"],
            identity=data["identity"],
            unlock_secret=data["unlock_secret"],
            profile_dir="/data/profile",
            worker_file=str(worker_path),
        )
        result = asyncio.run(run_trial(adapter))
        # A smoke test can pass even when an intermittent RPC failure occurs,
        # as long as the protocol stayed usable and a subsequent read worked.
        good = result["success"] >= 4 and result["statuses"][-1] == 0
        print("LIVE_GATE_RESULT:", "PASS" if good else "REVIEW_REQUIRED")
        return 0 if good else 1
    except Exception:
        print("LIVE_GATE_RESULT: BLOCKED")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
