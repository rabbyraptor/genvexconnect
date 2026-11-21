#!/usr/bin/env python3
"""Manual real RPC45 -> private HTTP -> running HA Core one-shot operator.

Run on HAOS host in an interactive SSH TTY. No installation or polling.
Credentials are prompted locally and sent only over Docker stdin. The IPC
token is random for this test, also delivered only by stdin. The Core
container runs a stdlib read-only probe; no HA registry/config mutation.
"""
from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

from haos_live_once_operator import (preflight, prompt_settings,
                                     check_file, require)
from haos_core_ipc_network_operator import (select_core_network,
                                            core_network_mode, run)

SOURCE = Path("/tmp/genvex-dev3-once/ipc_core_live_once.py")
CORE = "homeassistant"
MAX_WAIT_SECONDS = 112
# Runtime stdout is never forwarded. Only these literal, non-sensitive
# diagnostic markers are permitted to reach the operator terminal.
CHILD_FAILURE_CODES = frozenset({
    "INPUT_OR_PROFILE_INVALID", "INVALID_ARGUMENTS",
    "IPC_CORE_LIVE_ONCE_FAILED", "SDK_PROCESS_FAILURE",
    "SDK_TIMEOUT", "SDK_STARTUP_FAILED", "SDK_RESOURCES_FAILED",
    "SDK_SESSION_FAILED", "SDK_XML_FAILED", "SDK_RPC45_FAILED",
    "SDK_RESPONSE_INVALID", "SDK_CLOSE_FAILED", "SDK_EARLY_EXIT",
    "SDK_SNAPSHOT_INVALID",
})


class OperatorFailure(Exception):
    """Fixed category only; never store arbitrary Docker or SDK output."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def classify_runtime_exit(proc) -> OperatorFailure:
    """Inspect only 512 bytes of fixed-category child stdout on exit."""
    try:
        raw = proc.stdout.read(513) if proc.stdout is not None else b""
        if len(raw) <= 512:
            messages = raw.decode("ascii", "strict").splitlines()
            if (proc.returncode == 0 and messages ==
                    ["PASS: one RPC45 snapshot service expired and stopped"]):
                return OperatorFailure("RUNTIME_SERVED_BUT_CORE_WINDOW_MISSED")
            for code in CHILD_FAILURE_CODES:
                if messages == ["BLOCKED: " + code]:
                    return OperatorFailure(code)
    except (OSError, UnicodeError, AttributeError):
        pass
    return OperatorFailure("RUNTIME_EXITED_WITHOUT_SAFE_DIAGNOSTIC")


# Executed using python3 -c in the running HA Core container. No SDK or
# credentials appear in argv/env. The short-lived bearer token and exact
# device ID are supplied to this client as one bounded stdin line.
CORE_CLIENT = r"""
from datetime import datetime, timezone
from http.client import HTTPConnection
import json
import math
import sys

target = sys.argv[1]
port = int(sys.argv[2]) if len(sys.argv) > 2 else 18275
line = sys.stdin.buffer.readline(512)
if len(line) > 511 or not line.endswith(b"\n") or sys.stdin.buffer.read(1):
    raise ValueError("Invalid bounded IPC input")
settings = json.loads(line)
if set(settings) != {"device_id", "ipc_token"}:
    raise ValueError("Unexpected IPC input")
device = settings["device_id"]
token = settings["ipc_token"]

def check(auth, path, expected):
    conn = HTTPConnection(target, port, timeout=3)
    try:
        headers = {"Accept": "application/json"}
        if auth is not None:
            headers["Authorization"] = "Bearer " + auth
        conn.request("GET", path, headers=headers)
        reply = conn.getresponse()
        body = reply.read(4097)
        if len(body) > 4096 or reply.status != expected:
            raise ValueError("Unexpected IPC response")
        if reply.getheader("Cache-Control") != "no-store":
            raise ValueError("IPC cache policy")
        result = json.loads(body)
        if expected == 401:
            if result != {"error": "unauthorized"}:
                raise ValueError("Unauthorized response")
        elif expected == 404:
            if result != {"error": "not_found"}:
                raise ValueError("Unexpected route response")
        else:
            if set(result) != {
                "schema_version", "device_id", "timestamp_utc",
                "health", "values",
            } or result["schema_version"] != 1:
                raise ValueError("Snapshot envelope")
            if result["device_id"] != device or result["health"] != "ok":
                raise ValueError("Wrong device or health")
            measured = datetime.fromisoformat(
                result["timestamp_utc"].replace("Z", "+00:00")
            )
            if measured.tzinfo is None:
                raise ValueError("Naive timestamp")
            age = (datetime.now(timezone.utc) - measured).total_seconds()
            if not -30 <= age <= 180:
                raise ValueError("Stale or future snapshot")
            values = result["values"]
            if not isinstance(values, dict) or set(values) != {
                "supply_air", "outdoor_air", "exhaust_air",
                "extract_air", "humidity",
            }:
                raise ValueError("Incomplete snapshot")
            if any(type(value) not in (float, int) or not math.isfinite(value)
                   for value in values.values()):
                raise ValueError("Invalid reading")
    finally:
        conn.close()

wrong = ("x" if token[0] != "x" else "y") + token[1:]
check(None, "/v1/snapshot", 401)
check(wrong, "/v1/snapshot", 401)
check(token, "/v1/snapshot", 200)
check(token, "/v1/not-a-route", 404)
print("PASS: one real Genvex RPC45 snapshot reached HA Core over private HTTP")
"""


def private_address(name: str, network: str) -> str | None:
    inspected = run(["docker", "inspect", "--type", "container", name])
    if inspected.returncode != 0:
        return None
    info = json.loads(inspected.stdout)
    require(len(info) == 1, "Ambiguous disposable container")
    target = (((info[0].get("NetworkSettings") or {}).get("Networks") or {})
              .get(network, {}).get("IPAddress", ""))
    if not target:
        return None
    address = ipaddress.ip_address(target)
    require(isinstance(address, ipaddress.IPv4Address) and address.is_private
            and not address.is_loopback and not address.is_link_local,
            "Unexpected private runtime address")
    return target


def operator() -> int:
    require(os.geteuid() == 0, "Root required")
    check_file(SOURCE, 0o600)
    image = preflight()
    require(select_core_network() == "hassio",
            "Expected the verified Supervisor bridge")
    require(core_network_mode() == "host",
            "Expected verified HA Core host networking")
    print("LIVE CORE ONCE: one RPC45 -> validated private HTTP -> Core read; no polling",
          flush=True)
    settings = json.loads(prompt_settings())
    token = secrets.token_urlsafe(32)
    payload = json.dumps({**settings, "ipc_token": token},
                         separators=(",", ":")).encode("utf-8") + b"\n"
    core_payload = json.dumps(
        {"device_id": settings["device_id"], "ipc_token": token},
        separators=(",", ":"),
    ).encode("ascii") + b"\n"
    name = "genvex-dev3-core-live-" + secrets.token_hex(6)
    cmd = [
        "docker", "run", "--rm", "-i",
        "--name", name, "--network", "hassio",
        "--read-only", "--user", "0:0",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--pids-limit", "64", "--memory", "512m",
        "--log-driver", "none",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=64m,mode=700",
        "--mount",
        "type=bind,src=/mnt/data/supervisor/apps/data/local_genvex_nabto_remote/profile,dst=/data/profile,readonly",
        "--mount",
        "type=bind,src=/tmp/genvex-dev3-once/live_once.py,dst=/opt/genvex-remote/runtime/live_once.py,readonly",
        "--mount",
        "type=bind,src=/tmp/genvex-dev3-once/sdk_snapshot_adapter.py,dst=/opt/genvex-remote/runtime/sdk_snapshot_adapter.py,readonly",
        "--mount",
        f"type=bind,src={SOURCE},dst=/opt/genvex-remote/runtime/ipc_core_live_once.py,readonly",
        "--entrypoint", "/usr/bin/python3", image,
        "/opt/genvex-remote/runtime/ipc_core_live_once.py",
    ]
    proc = None
    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        require(proc.stdin is not None, "No disposable runtime stdin")
        try:
            proc.stdin.write(payload)
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            raise OperatorFailure("CONTAINER_START_OR_STDIN_FAILED") from None
        proc.stdin = None  # read after exit must not flush closed stdin
        deadline = time.monotonic() + MAX_WAIT_SECONDS
        target = None
        had_client_attempt = False
        client_timed_out = False
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise classify_runtime_exit(proc)
            if target is None:
                target = private_address(name, "hassio")
            if target is not None:
                had_client_attempt = True
                try:
                    result = run(
                        ["docker", "exec", "-i", CORE, "python3", "-c",
                         CORE_CLIENT, target],
                        timeout=14, input=core_payload,
                    )
                except subprocess.TimeoutExpired:
                    # An unresponsive Core HTTP request is not an SDK retry.
                    client_timed_out = True
                    continue
                if result.returncode == 0:
                    require(result.stdout.strip() ==
                            b"PASS: one real Genvex RPC45 snapshot reached HA Core over private HTTP",
                            "Unexpected Core validation output")
                    print(result.stdout.decode("ascii").strip(), flush=True)
                    return 0
            time.sleep(2)
        if proc.poll() is not None:
            raise classify_runtime_exit(proc)
        if target is None:
            raise OperatorFailure("PRIVATE_BRIDGE_ADDRESS_NOT_FOUND")
        if client_timed_out:
            raise OperatorFailure("CORE_HTTP_PROBE_TIMEOUT")
        if had_client_attempt:
            raise OperatorFailure("CORE_HTTP_SNAPSHOT_NOT_VALIDATED")
        raise OperatorFailure("CORE_READ_NOT_ATTEMPTED")
    finally:
        # docker run -i can outlive its CLI; remove the exact random-name
        # container even after user cancellation or a transport timeout.
        run(["docker", "rm", "-f", name], timeout=15)
        if proc is not None:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


def main() -> int:
    if sys.argv[1:]:
        print("BLOCKED: unsupported options", flush=True)
        return 1
    try:
        return operator()
    except OperatorFailure as error:
        print("BLOCKED: " + error.code, flush=True)
        return 1
    except (KeyboardInterrupt, Exception):
        # Do not reflect exception details, stdout/stderr, or credentials.
        print("BLOCKED: OPERATOR_PROCESS_FAILURE", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
