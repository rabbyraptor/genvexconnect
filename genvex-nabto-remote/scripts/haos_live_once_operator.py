#!/usr/bin/env python3
"""HAOS host operator launcher for a single isolated read-only RPC45 probe.

Run ONLY through an interactive SSH TTY on the HAOS host after copying this
reviewed file and live_once.py into a private root-owned staging directory.
Credentials are prompted on the TTY; they never enter argv, shell history,
environment variables, an App option or a host file.
"""
from __future__ import annotations

import getpass
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys
import time

APP = "local_genvex_nabto_remote"
PROFILE = Path("/mnt/data/supervisor/apps/data") / APP / "profile"
RUNNER = Path("/tmp/genvex-dev3-once/live_once.py")
ADAPTER = Path("/tmp/genvex-dev3-once/sdk_snapshot_adapter.py")
IMAGE_CONTAINER = "app_" + APP
LIMIT = 110
TRIAL_ATTEMPTS = 3
TRIAL_GAP_SECONDS = 60


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def check_file(path, mode, directory=False):
    s = path.lstat()
    require(
        (stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode))
        and s.st_uid == 0 and stat.S_IMODE(s.st_mode) == mode,
        "Unsafe staging or profile permissions",
    )


def checked_image():
    result = subprocess.run(
        ["ha", "apps", "info", APP, "--raw-json"],
        capture_output=True, text=True, timeout=30, check=True,
    )
    info = json.loads(result.stdout)
    require(info.get("result") == "ok", "Supervisor unavailable")
    app = info["data"]
    require(app.get("version") == "0.1.0-dev2", "Unexpected App version")
    require(app.get("state") == "stopped", "App must be stopped")
    require(app.get("boot") == "manual", "App must remain manual")
    options = app["options"]
    require(options.get("diagnostic_only") is True, "Diagnostic safety flag absent")
    require(all(options.get(k) == "" for k in (
        "device_id", "identity", "unlock_secret", "ipc_token",
    )), "App credentials unexpectedly populated")

    # Supervisor may delete the stopped App container. Resolve the pinned local
    # image without starting or creating a Supervisor-managed container.
    containers = subprocess.run(
        ["docker", "inspect", "--type", "container", IMAGE_CONTAINER],
        capture_output=True, text=True, timeout=20, check=False,
    )
    if containers.returncode == 0:
        found = json.loads(containers.stdout)
        require(len(found) == 1, "Unexpected App container count")
        require(not found[0]["State"]["Running"], "App container is running")

    listed = subprocess.run(
        ["docker", "image", "ls", "--no-trunc", "--format", "{{json .}}"],
        capture_output=True, text=True, timeout=20, check=True,
    )
    candidates = set()
    for line in listed.stdout.splitlines():
        item = json.loads(line)
        repository = item.get("Repository", "")
        tag = item.get("Tag", "")
        image_id = item.get("ID", "")
        # Local Home Assistant builds use a local/ image repository.
        if (repository.startswith("local/")
                and ("genvex_nabto_remote" in repository
                     or "genvex-nabto-remote" in repository)
                and tag == "0.1.0-dev2"
                and isinstance(image_id, str)
                and image_id.startswith("sha256:")):
            candidates.add(image_id)

    require(len(candidates) == 1, "Missing or ambiguous local DEV2 image")
    image_id = next(iter(candidates))
    inspected = subprocess.run(
        ["docker", "image", "inspect", image_id],
        capture_output=True, text=True, timeout=20, check=True,
    )
    image_info = json.loads(inspected.stdout)
    require(len(image_info) == 1, "Unexpected image inspection")
    image = image_info[0]
    require(image.get("Id") == image_id, "Image ID changed")
    require(image.get("Architecture") == "arm64", "Wrong image architecture")
    labels = (image.get("Config") or {}).get("Labels") or {}
    require(labels.get("io.hass.version") == "0.1.0-dev2",
            "Unexpected image version label")
    require(labels.get("io.hass.type") == "app", "Unexpected image type")
    return image_id


def preflight():
    require(os.geteuid() == 0, "Root access required")
    check_file(PROFILE, 0o700, directory=True)
    require({p.name for p in PROFILE.iterdir()} == {
        "client.crt", "client-encrypted.key",
    }, "Unexpected profile contents")
    for name in ("client.crt", "client-encrypted.key"):
        check_file(PROFILE / name, 0o600)
    check_file(RUNNER.parent, 0o700, directory=True)
    check_file(RUNNER, 0o600)
    check_file(ADAPTER, 0o600)
    return checked_image()


def prompt_settings():
    print("Enter values locally in the SSH terminal. Input is hidden.")
    device_id = getpass.getpass("12-digit device ID: ")
    identity = getpass.getpass("Nabto identity (email): ")
    secret = getpass.getpass("Encrypted key unlock secret: ")
    require(len(device_id) == 12 and device_id.isascii() and
            device_id.isdecimal(), "Invalid device ID")
    for value in (identity, secret):
        require(1 <= len(value) <= 1024 and
                not any(ch in value for ch in "\r\n\x00"),
                "Invalid credential")
    return json.dumps(
        {"device_id": device_id, "identity": identity,
         "unlock_secret": secret}, separators=(",", ":"),
    ).encode() + b"\n"


def run_once(image, payload, *, show_values=False, diagnose=False):
    name = "genvex-rpc45-once-" + secrets.token_hex(6)
    cmd = [
        "docker", "run", "--rm", "-i",
        "--name", name,
        "--network", "bridge",
        "--read-only", "--user", "0:0",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--pids-limit", "64",
        "--memory", "512m",
        "--log-driver", "none",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=64m,mode=700",
        "--mount", f"type=bind,src={PROFILE},dst=/data/profile,readonly",
        "--mount",
        f"type=bind,src={RUNNER},dst=/opt/genvex-remote/runtime/live_once.py,readonly",
        "--mount",
        f"type=bind,src={ADAPTER},dst=/opt/genvex-remote/runtime/sdk_snapshot_adapter.py,readonly",
        "--entrypoint", "/usr/bin/python3",
        image, "/opt/genvex-remote/runtime/live_once.py",
    ]
    if show_values:
        cmd.append("--show-values")
    if diagnose:
        cmd.append("--diagnose")
    try:
        done = subprocess.run(cmd, input=payload, timeout=LIMIT, check=False)
        require(done.returncode == 0, "Single-shot container reported failure")
    finally:
        # A killed Docker CLI can leave its detached child alive: force cleanup.
        subprocess.run(
            ["docker", "rm", "-f", name],
            capture_output=True, timeout=15, check=False,
        )


def bounded_trial(image, payload, *, sleep=time.sleep, diagnose=False):
    """Exactly three disposable reads, with no retries or persistent daemon.

    Each attempt is independently isolated. Never print credentials or
    vendor diagnostics; a failed read counts as failed and does not trigger
    an immediate extra request.
    """
    passed = 0
    for attempt in range(1, TRIAL_ATTEMPTS + 1):
        require(preflight() == image, "App or image changed during trial")
        try:
            if diagnose:
                run_once(image, payload, diagnose=True)
            else:
                run_once(image, payload)
        except (RuntimeError, subprocess.TimeoutExpired, OSError):
            print(f"TRIAL {attempt}/{TRIAL_ATTEMPTS}: FAILED", flush=True)
        else:
            passed += 1
            print(f"TRIAL {attempt}/{TRIAL_ATTEMPTS}: PASS", flush=True)
        if attempt < TRIAL_ATTEMPTS:
            sleep(TRIAL_GAP_SECONDS)
    print(f"TRIAL SUMMARY: {passed}/{TRIAL_ATTEMPTS} validated", flush=True)
    return passed == TRIAL_ATTEMPTS


def main():
    try:
        require(sys.argv[1:] in ([], ["--show-values"], ["--trial-three"],
                                   ["--diagnose"], ["--trial-diagnose"]),
                "Unsupported display option")
        show_values = sys.argv[1:] == ["--show-values"]
        trial = sys.argv[1:] in (["--trial-three"], ["--trial-diagnose"])
        diagnose = sys.argv[1:] in (["--diagnose"], ["--trial-diagnose"])
        image = preflight()
        print("PASS: DEV2 stopped; profile read-only; separate container selected")
        if trial:
            print("TRIAL: exactly three read-only RPC45 batches, >=60 s apart; Ctrl-C aborts", flush=True)
        payload = prompt_settings()
        if trial:
            if not bounded_trial(image, payload, diagnose=diagnose):
                print("BLOCKED: bounded trial had one or more failed reads", flush=True)
                return 1
        else:
            run_once(image, payload, show_values=show_values, diagnose=diagnose)
        print("PASS: isolated container exited; DEV2 remained untouched")
        return 0
    except (Exception, KeyboardInterrupt):
        print("BLOCKED: one-shot test did not complete (details suppressed)")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
