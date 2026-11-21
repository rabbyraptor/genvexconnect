"""Execute the exact ephemeral HAOS Core class-probe program in isolation.

The real HA component sources are injected into an *independent* Python
interpreter that has the pinned HA Core packages installed. A real TCP
listener serves fake readings only on 127.0.0.1. No device, secrets or
running Home Assistant installation is involved.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys


import pytest

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "genvex-nabto-remote" / "runtime"
SCRIPTS = ROOT / "genvex-nabto-remote" / "scripts"
COMPONENT = ROOT / "experimental" / "home_assistant" / "custom_components" / "genvex_remote"
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(SCRIPTS))

import haos_core_live_entity_once_operator as probe
from polling_http_server import SnapshotHTTPServer

DEVICE = "123456789012"
TOKEN = "M" * 48
PASS = b"PASS: one real Genvex RPC45 snapshot reached HA Core over private HTTP\n"


def snapshot():
    return {
        "schema_version": 1,
        "device_id": DEVICE,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "health": "ok",
        "values": {
            "supply_air": 12.4, "outdoor_air": 2.1,
            "exhaust_air": 9.3, "extract_air": 10.6,
            "humidity": 58.0,
        },
    }


def test_actual_core_classes_in_memory_read_real_loopback_tcp(socket_enabled):
    sources = {
        name: (COMPONENT / (name + ".py")).read_text(encoding="utf-8")
        for name in probe.MODULES
    }
    compiled = probe.build_core_client(sources)
    assert 'local-genvex-nabto-remote' in compiled
    assert "genvex_remote_probe" in compiled
    assert "not-a-secret" not in compiled

    provider_calls = []
    def provide():
        provider_calls.append(True)
        return snapshot()

    server = SnapshotHTTPServer(
        bind_host="127.0.0.1", port=0, token=TOKEN,
        device_id=DEVICE, snapshot_provider=provide,
    )
    try:
        port = server._server.server_address[1]
        server.start()
        result = subprocess.run(
            [sys.executable, "-c", compiled, "127.0.0.1", str(port)],
            input=json.dumps({"device_id": DEVICE, "ipc_token": TOKEN}).encode() + b"\n",
            capture_output=True, timeout=30, check=False,
        )
        assert result.returncode == 0, (
            result.stdout.decode(errors="replace"),
            result.stderr.decode(errors="replace")[-600:],
        )
        assert result.stdout == PASS
        assert len(provider_calls) == 2  # one stdlib GET, then real HA reader
        assert TOKEN.encode() not in result.stdout + result.stderr
        assert DEVICE.encode() not in result.stdout + result.stderr
    finally:
        server.stop()


def test_source_loader_fails_closed_on_wrong_module_set():
    with pytest.raises(ValueError):
        probe.build_core_client({"runtime_client": "pass"})
