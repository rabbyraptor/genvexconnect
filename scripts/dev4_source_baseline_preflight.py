#!/usr/bin/env python3
"""Read-only DEV3 installed source verification before a DEV4 transaction.

Git blob identities of the exact deployed DEV3 source commit are pinned.
No credentials, live RPC, Supervisor options, or mutations are needed.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys

BASELINE_COMMIT = "d7ad38a60991cca1a4f4b3af677ee501d749f74c"
APP = "app_local_genvex_nabto_remote"
SLUG = "local_genvex_nabto_remote"
SOURCE = Path("/mnt/data/supervisor/apps/local/genvex_nabto_remote")
EXPECTED = {
  "Dockerfile": [
    "c91923037f1f879ef1b8ed8394f0046774ae002c",
    4353
  ],
  "config.yaml": [
    "5312eed6bc02437c7ee03042ffd884a64f3a8d0e",
    686
  ],
  "run.sh": [
    "d5384bb01bf93fa347d5fa61c3773a819c4cac44",
    109
  ],
  "runtime/app_bootstrap.py": [
    "ffcb8f81744c35c46f21b694de576c8440cf7faa",
    6226
  ],
  "runtime/diagnostic_http_server.py": [
    "1fad502d212345beb7d5b42c18e34f382b88fc95",
    3653
  ],
  "runtime/ipc_auth.py": [
    "78c0574f017b3987fc2e3b4ad792c040ebd4e88a",
    1179
  ],
  "runtime/ipc_core_live_once.py": [
    "77a727ebd4ad82c0fc26b84f47cdd96451afa41f",
    4145
  ],
  "runtime/ipc_once.py": [
    "75e455def4f917a88ded78c3ca8ef36b66ba7995",
    3881
  ],
  "runtime/ipc_web_candidate.py": [
    "a6cff70f79bc812f4b73a979faab05f1b938f9e0",
    3406
  ],
  "runtime/live_once.py": [
    "4d6ddec67f246cc8005b23827c679213e2798191",
    5917
  ],
  "runtime/offline_ipc_network_smoke.py": [
    "6c70b7bd3944c9ebe757f05f5db53e0f5eb5a439",
    4012
  ],
  "runtime/polling_http_server.py": [
    "2c3533cf9674f8d7160e086e209696d75941e630",
    3871
  ],
  "runtime/polling_runtime.py": [
    "6590c43fcd422c226c0c9586cc3cfc056a9751fb",
    3386
  ],
  "runtime/polling_service.py": [
    "a54c33347f875ecc0f37d6e5c375edc0919ac2bf",
    2509
  ],
  "runtime/polling_worker.py": [
    "4860c08ebe8bde705f50271204efb3c2edc452b8",
    2395
  ],
  "runtime/probe_remote_snapshot.py": [
    "31744afe87bad8eae349f695925ecacd0e455f6d",
    9073
  ],
  "runtime/profile_provision.py": [
    "c36fcfe9e51d75ee3dc9ec2d6801dd776cd42173",
    6615
  ],
  "runtime/recovery_policy.py": [
    "1b143413759e27e32beaf240f09605c3f93e2990",
    1914
  ],
  "runtime/sdk_snapshot_adapter.py": [
    "2b55624e31331596135eb7dc8068a39a932760f7",
    11622
  ],
  "runtime/sensor_model.py": [
    "a2f1ee7fc363654b6320d1d707472566f90b889b",
    2054
  ],
  "runtime/snapshot_api.py": [
    "054ad899b6132a1df4fc37a7862f9c47a1d23f91",
    1982
  ],
  "runtime/snapshot_contract.py": [
    "e276b5d21ebd646138dbaf85ebc5527ece2bc974",
    2766
  ],
  "runtime/snapshot_state.py": [
    "34e1c6e36824a8bd5aa4e08dd15cfe3c4fd7d3c2",
    2809
  ]
}


class PreflightError(Exception):
    pass


def verify_source_tree(directory: Path, expected: dict = EXPECTED) -> int:
    if directory.is_symlink() or not directory.is_dir():
        raise PreflightError("SOURCE_DIRECTORY")
    paths = list(directory.rglob("*"))
    actual = set()
    for item in paths:
        relative = item.relative_to(directory).as_posix()
        if item.is_symlink():
            raise PreflightError("SOURCE_LINK")
        if item.is_dir():
            if relative != "runtime":
                raise PreflightError("UNEXPECTED_DIRECTORY")
            continue
        if not item.is_file() or not stat.S_ISREG(item.stat().st_mode):
            raise PreflightError("NONREGULAR_SOURCE")
        actual.add(relative)
    if actual != set(expected):
        raise PreflightError("SOURCE_INVENTORY")
    for name, (sha, size) in expected.items():
        candidate = directory / name
        content = candidate.read_bytes()
        if len(content) != size:
            raise PreflightError("SOURCE_FILE_SIZE")
        git_sha = hashlib.sha1(
            b"blob " + str(len(content)).encode("ascii") + b"\x00" + content
        ).hexdigest()
        if git_sha != sha:
            raise PreflightError("SOURCE_BLOB_MISMATCH")
    return len(expected)


def run_json(command: list[str]) -> dict:
    result = subprocess.run(command, text=True, capture_output=True, timeout=35)
    if result.returncode:
        raise PreflightError("METADATA_UNAVAILABLE")
    try:
        return json.loads(result.stdout)
    except ValueError:
        raise PreflightError("INVALID_METADATA") from None


def main() -> int:
    if sys.argv[1:] != ["--execute-readonly"]:
        return 2
    print("===== DEV4 SOURCE BASELINE PREFLIGHT =====", flush=True)
    try:
        info = run_json(["ha", "apps", "info", SLUG, "--raw-json"])["data"]
        if not isinstance(info, dict):
            raise PreflightError("APP_METADATA")
        checks = {
            "DEV3_VERSION": info.get("version") == "0.1.0-dev3",
            "MANUAL_BOOT": info.get("boot") == "manual",
            "VALID_STATE": info.get("state") in ("started", "stopped"),
        }
        docker = run_json([
            "docker", "inspect", APP, "--format", "{{json .}}",
        ])
        if not isinstance(docker, dict):
            raise PreflightError("CONTAINER_METADATA")
        checks["APP_CONTAINER_MATCHES_STATE"] = bool(
            docker["State"]["Running"]
        ) == (info.get("state") == "started")
        checks["APP_PRIVATE_NETWORK"] = set(
            docker["NetworkSettings"]["Networks"]
        ) == {"hassio"}
        checks["NO_PUBLISHED_PORTS"] = not bool(
            docker["HostConfig"].get("PortBindings")
        )
        old_backup = SOURCE.parent / ".genvex-remote-dev3-source-backup"
        stage = SOURCE.parent / ".genvex-remote-dev4-source-stage"
        checks["DEV4_TRANSACTION_PATHS_AVAILABLE"] = all(
            not p.exists() and not p.is_symlink()
            for p in (old_backup, stage)
        )
        for key, value in checks.items():
            print(key + ":", "PASS" if value else "FAIL", flush=True)
        if not all(checks.values()):
            print("GATE_P3_RESULT: REVIEW_REQUIRED")
            return 1
        count = verify_source_tree(SOURCE)
        print("PINNED_DEV3_SOURCE_COMMIT:", BASELINE_COMMIT)
        print("EXACT_SOURCE_FILES:", count)
        print("SOURCE_BLOB_VERIFICATION: PASS")
        print("GATE_P3_RESULT: PASS")
        return 0
    except (PreflightError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as err:
        print("GATE_P3_RESULT: BLOCKED")
        print("ERROR_CATEGORY:", err.args[0] if isinstance(err, PreflightError) else type(err).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
