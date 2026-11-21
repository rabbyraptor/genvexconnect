#!/usr/bin/env python3
"""One-time fake-only HA Core -> disposable private Docker IPC test.

Execute locally on the HAOS host as root. It starts no Nabto RPC or
poller, installs nothing, and never copies a credential into Home Assistant.
Only a small stdlib Python probe is executed inside the existing Core
container; the HTTP server is force-removed on every exit path.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import time
import subprocess
import sys

from haos_live_once_operator import checked_image, check_file, require

SOURCE = Path("/tmp/genvex-dev3-once/offline_ipc_network_smoke.py")
CORE_NAME = "homeassistant"
TIMEOUT = 25

# This executable runs in the existing Core container via docker exec -i.
# The token and all five readings are SYNTHETIC, never real credentials.
# Only PASS/FAIL is returned, without forwarding snapshot content.
CLIENT = r"""
import http.client
import json
import sys

alias = sys.argv[1]
port = 18275
token = "T" * 43

def check(auth, path, wanted):
    conn = http.client.HTTPConnection(alias, port, timeout=3)
    try:
        headers = {"Accept": "application/json"}
        if auth is not None:
            headers["Authorization"] = "Bearer " + auth
        conn.request("GET", path, headers=headers)
        response = conn.getresponse()
        raw = response.read(4097)
        assert len(raw) <= 4096
        assert response.status == wanted
        assert response.getheader("Cache-Control") == "no-store"
        data = json.loads(raw)
        if wanted == 200:
            assert data["schema_version"] == 1
            assert data["device_id"] == "123456789012"
            assert data["health"] == "ok"
            assert set(data["values"]) == {
                "supply_air", "outdoor_air", "exhaust_air",
                "extract_air", "humidity",
            }
            assert data["values"]["humidity"] == 55.0
        elif wanted == 401:
            assert data == {"error": "unauthorized"}
        else:
            assert data == {"error": "not_found"}
    finally:
        conn.close()

check(None, "/v1/snapshot", 401)
check("X" * 43, "/v1/snapshot", 401)
check(token, "/v1/snapshot", 200)
check(token, "/v1/snapshot?debug=1", 404)
print("PASS: HA Core container reached authenticated private IPC; 401/200/404")
"""


def run(args: list[str], *, timeout: int = TIMEOUT, input: bytes | None = None):
    return subprocess.run(args, capture_output=True, input=input,
                          timeout=timeout, check=False)


def select_core_network() -> str:
    raw = run(["docker", "inspect", "--type", "container", CORE_NAME])
    require(raw.returncode == 0, "Home Assistant Core container not found")
    info = json.loads(raw.stdout)
    require(len(info) == 1, "Ambiguous Core container")
    core = info[0]
    require(core["State"]["Running"], "Home Assistant Core is not running")
    networks = (core.get("NetworkSettings") or {}).get("Networks") or {}
    allowed = [name for name in networks
               if name not in ("bridge", "host", "none")]
    require(len(allowed) > 0, "No private Core Docker network")
    # Prefer Supervisor's application bridge when present, otherwise
    # require one unambiguous private Docker network.
    if "hassio" in allowed:
        name = "hassio"
    else:
        require(len(allowed) == 1, "Ambiguous private Core networks")
        name = allowed[0]
    check = run(["docker", "network", "inspect", name])
    require(check.returncode == 0, "Cannot inspect private Docker network")
    details = json.loads(check.stdout)
    require(len(details) == 1, "Ambiguous network inspection")
    require(details[0].get("Driver") == "bridge",
            "Unexpected network driver")
    require(details[0].get("Scope") == "local",
            "Unexpected network scope")
    return name


def operator() -> int:
    require(os.geteuid() == 0, "Root access required")
    check_file(SOURCE.parent, 0o700, directory=True)
    check_file(SOURCE, 0o600)
    image = checked_image()
    network = select_core_network()
    suffix = secrets.token_hex(5)
    name = "genvex-dev3-ipc-net-" + suffix
    alias = "genvex-dev3-ipc-" + suffix
    cmd = [
        "docker", "run", "-d", "--rm",
        "--name", name, "--network", network,
        "--network-alias", alias,
        "--read-only", "--user", "0:0",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--pids-limit", "32", "--memory", "128m",
        "--log-driver", "none",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=16m,mode=700",
        "--mount",
        f"type=bind,src={SOURCE},dst=/opt/genvex-remote/runtime/offline_ipc_network_smoke.py,readonly",
        "--entrypoint", "/usr/bin/python3",
        image,
        "/opt/genvex-remote/runtime/offline_ipc_network_smoke.py",
        "serve", "available",
    ]
    print("TEST: private Supervisor network; fake-only IPC; no Nabto requests",
          flush=True)
    try:
        started = run(cmd)
        require(started.returncode == 0,
                "Private IPC test container could not start")
        # Docker networking and container startup may take a moment. Retrying
        # only this fake TCP check cannot issue any Nabto requests.
        probe = None
        for attempt in range(5):
            probe = run(
                ["docker", "exec", "-i", CORE_NAME, "python3", "-", alias],
                timeout=12, input=CLIENT.encode("utf-8"),
            )
            if probe.returncode == 0:
                break
            if attempt < 4:
                time.sleep(1)
        require(probe is not None and probe.returncode == 0,
                "Core-to-App private TCP test failed")
        require(probe.stdout.strip() ==
                b"PASS: HA Core container reached authenticated private IPC; 401/200/404",
                "Unexpected Core test result")
        print(probe.stdout.decode("ascii").strip(), flush=True)
        return 0
    finally:
        run(["docker", "rm", "-f", name], timeout=15)


def main() -> int:
    if sys.argv[1:] != []:
        print("BLOCKED: unexpected options", flush=True)
        return 1
    try:
        return operator()
    except (Exception, KeyboardInterrupt):
        print("BLOCKED: Core private IPC test failed; details suppressed", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
