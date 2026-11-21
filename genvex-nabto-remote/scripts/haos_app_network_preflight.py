#!/usr/bin/env python3
"""Read-only HAOS App network/DNS preflight. No credentials or SDK requests.

Run on HAOS host. Fixed diagnostic markers only; never print raw Docker
inspect, Supervisor output, container IPs, environment or configuration.
The installed App may be stopped; that is an expected separate gate.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

APP_SLUG = "local_genvex_nabto_remote"
APP_CONTAINER = "app_local_genvex_nabto_remote"
CORE_CONTAINER = "homeassistant"
EXPECTED_HOST = "local-genvex-nabto-remote"
MAX_OUTPUT = 131072


def command(*args: str) -> tuple[int, str]:
    try:
        result = subprocess.run(
            list(args), capture_output=True, timeout=12, check=False,
        )
        if len(result.stdout) > MAX_OUTPUT:
            return 1, ""
        return result.returncode, result.stdout.decode("utf-8", "strict")
    except (OSError, UnicodeError, subprocess.TimeoutExpired):
        return 1, ""


def inspect(name: str) -> dict | None:
    status, output = command("docker", "inspect", "--type", "container", name)
    if status:
        return None
    try:
        items = json.loads(output)
        if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
            return None
        return items[0]
    except (ValueError, TypeError):
        return None


def network_names(info: dict) -> set[str]:
    networks = (info.get("NetworkSettings") or {}).get("Networks") or {}
    return set(networks) if isinstance(networks, dict) else set()


def check_app_metadata() -> tuple[bool, bool]:
    """Return (known, stopped). Never read or print App options."""
    status, output = command("ha", "apps", "info", APP_SLUG, "--raw-json")
    if status:
        print("BLOCKED: APP_METADATA_UNAVAILABLE")
        return False, False
    try:
        metadata = json.loads(output)
        if not isinstance(metadata, dict):
            raise ValueError
        if metadata.get("result") != "ok" or not isinstance(metadata.get("data"), dict):
            raise ValueError
        metadata = metadata["data"]
        slug = metadata.get("slug")
        if slug not in (APP_SLUG, "genvex_nabto_remote"):
            raise ValueError
        boot = metadata.get("boot")
        network = metadata.get("host_network")
        if boot != "manual" or network is True:
            print("BLOCKED: APP_SAFETY_SETTINGS_MISMATCH")
            return False, False
        state = metadata.get("state")
        if state not in ("stopped", "started", "error", "unknown"):
            print("BLOCKED: APP_STATE_UNRECOGNIZED")
            return False, False
        print("PASS: APP_METADATA_MANUAL_ONLY_PRIVATE_NETWORK")
        return True, state == "stopped"
    except (TypeError, ValueError):
        print("BLOCKED: APP_METADATA_UNEXPECTED")
        return False, False


def check_core() -> bool:
    core = inspect(CORE_CONTAINER)
    if core is None:
        print("BLOCKED: CORE_CONTAINER_UNAVAILABLE")
        return False
    if not (core.get("State") or {}).get("Running"):
        print("BLOCKED: CORE_NOT_RUNNING")
        return False
    mode = (core.get("HostConfig") or {}).get("NetworkMode")
    if mode != "host":
        print("BLOCKED: CORE_NETWORK_UNEXPECTED")
        return False
    print("PASS: CORE_RUNNING_HOST_NETWORK")
    return True


def check_app_container() -> None:
    app = inspect(APP_CONTAINER)
    if app is None:
        print("INFO: APP_CONTAINER_NOT_PRESENT_OR_STOPPED")
        return
    if (app.get("State") or {}).get("Running"):
        print("INFO: APP_CONTAINER_RUNNING_REQUIRES_SEPARATE_REVIEW")
        return
    if (app.get("HostConfig") or {}).get("NetworkMode") == "host":
        print("BLOCKED: APP_HOST_NETWORK")
        return
    published = (app.get("HostConfig") or {}).get("PortBindings") or {}
    if published:
        print("BLOCKED: APP_HOST_PORT_BINDING")
        return
    networks = network_names(app)
    if "hassio" not in networks:
        print("INFO: STOPPED_APP_PRIVATE_NETWORK_NOT_INSPECTABLE")
        return
    print("PASS: STOPPED_APP_NO_HOST_PORT_BINDINGS")


def check_dns() -> None:
    # Running Core's independent python3 -c process uses only stdlib
    # getaddrinfo. No connection, no HTTP, no Nabto and no config mutation.
    script = (
        "import socket,sys;"
        "name=sys.argv[1];"
        "try_dns=lambda:socket.getaddrinfo(name,18275,type=socket.SOCK_STREAM);"
        "addresses=try_dns();"
        "print('PASS: APP_DNS_RESOLVES' if addresses else 'INFO: APP_DNS_UNRESOLVED')"
    )
    status, output = command(
        "docker", "exec", CORE_CONTAINER, "python3", "-c", script, EXPECTED_HOST,
    )
    if status == 0 and output.strip() == "PASS: APP_DNS_RESOLVES":
        print("PASS: APP_DNS_RESOLVES")
    else:
        print("INFO: APP_DNS_UNRESOLVED_OR_UNAVAILABLE")


def main() -> int:
    if sys.argv[1:] or os.geteuid() != 0:
        print("BLOCKED: ROOT_AND_NO_ARGUMENTS_REQUIRED")
        return 1
    print("HAOS APP NETWORK PREFLIGHT: read-only; no credentials; no RPC45")
    known, stopped = check_app_metadata()
    core_ok = check_core()
    if not known or not core_ok:
        print("BLOCKED: PREFLIGHT_INCOMPLETE")
        return 1
    if stopped:
        print("PASS: APP_STOPPED")
    else:
        print("INFO: APP_NOT_STOPPED_REQUIRES_REVIEW")
    check_app_container()
    check_dns()
    print("PASS: READ_ONLY_PREFLIGHT_FINISHED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
