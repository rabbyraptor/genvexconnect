#!/usr/bin/env python3
"""Experimental read-only runtime daemon, for isolated Docker/App use only.

Configuration file contains sensitive SDK identity and unlock passphrase.
Never publish the IPC port, mount a host Docker socket, or run on HA Core.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import stat
from pathlib import Path

from ipc_auth import authorize_read
from polling_http_server import SnapshotHTTPServer
from polling_service import PollingService
from sdk_snapshot_adapter import SDKSnapshotAdapter
from snapshot_state import SnapshotState


def load_config(path: Path) -> dict:
    if path.is_symlink():
        raise ValueError("Configuration must not be a symlink")
    mode = path.stat().st_mode
    if not stat.S_ISREG(mode) or mode & 0o077:
        raise ValueError("Configuration permissions must be 0600 or stricter")
    if path.stat().st_size > 4096:
        raise ValueError("Configuration too large")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {
        "device_id", "identity", "unlock_secret", "profile_dir",
        "probe_file", "token_file", "bind_host", "poll_seconds",
    }:
        raise ValueError("Invalid runtime configuration")
    if data["bind_host"] not in ("127.0.0.1", "0.0.0.0"):
        raise ValueError("Invalid bind address")
    return data


def read_token(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Invalid IPC token file")
    if path.stat().st_mode & 0o077 or path.stat().st_size > 256:
        raise ValueError("IPC token file must be private and small")
    token = path.read_text(encoding="ascii").strip()
    authorize_read(token, token)
    return token


async def run(config: dict) -> None:
    token = read_token(Path(config["token_file"]))
    adapter = SDKSnapshotAdapter(
        device_id=config["device_id"],
        identity=config["identity"],
        unlock_secret=config["unlock_secret"],
        profile_dir=config["profile_dir"],
        probe_file=config["probe_file"],
    )
    state = SnapshotState(adapter)
    poller = PollingService(state, interval_seconds=config["poll_seconds"])
    server = SnapshotHTTPServer(
        bind_host=config["bind_host"], port=18275, token=token,
        device_id=adapter.device_id, snapshot_provider=state.current,
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass
    try:
        await poller.start()
        server.start()
        print("Read-only runtime started (no public port required)", flush=True)
        await stop.wait()
    finally:
        await poller.stop()
        server.stop()
        print("Read-only runtime stopped", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-file", required=True, type=Path)
    args = parser.parse_args()
    try:
        config = load_config(args.config_file)
        asyncio.run(run(config))
    except Exception:
        # Never print config values, SDK diagnostics or credential material.
        raise SystemExit("Runtime failed; sensitive details suppressed")


if __name__ == "__main__":
    main()
