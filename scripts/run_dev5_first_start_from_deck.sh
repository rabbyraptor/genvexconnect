#!/usr/bin/env bash
# Explicit DEV5 first-start gate. Starts ONLY local_genvex_nabto_remote,
# then checks Supervisor state, worker count and a fresh authenticated IPC read.
# Does not print options, tokens, device ID, SDK response or sensor values.
set -euo pipefail
umask 077

OUT=$(mktemp)
trap 'rm -f -- "$OUT"' EXIT

run() {
ssh -T -p 22222 -o BatchMode=yes -o ServerAliveInterval=30 \
  root@rabbyshome.duckdns.org 'sh -s' <<'REMOTE'
set -eu
echo "===== DEV5 FIRST-START GATE ====="
python3 - <<'PY'
import json
from pathlib import Path
import subprocess

slug = "local_genvex_nabto_remote"
source = Path("/mnt/data/supervisor/apps/local/genvex_nabto_remote/config.yaml")
if not source.is_file() or b'version: "0.1.0-dev5"' not in source.read_bytes().splitlines():
    raise SystemExit("BLOCKED: DEV5_SOURCE_MANIFEST")
result = subprocess.run(
    ["ha", "apps", "info", slug, "--raw-json"],
    capture_output=True, text=True, timeout=60
)
if result.returncode:
    raise SystemExit("BLOCKED: SUPERVISOR_INFO")
try:
    info = json.loads(result.stdout)["data"]
    options = info["options"]
    valid = (
        info.get("version") == "0.1.0-dev5"
        and info.get("state") == "stopped"
        and info.get("boot") == "manual"
        and type(options) is dict
        and options.get("persistent_session") is True
        and options.get("poll_seconds") == 60
    )
except (KeyError, ValueError, TypeError):
    valid = False
if not valid:
    raise SystemExit("BLOCKED: DEV5_STATE_OR_OPTIONS")
print("DEV5_PRESTART: PASS")
PY

echo "START_DEV5: REQUESTED"
ha apps start local_genvex_nabto_remote >/dev/null
echo "START_DEV5: RETURNED"

python3 - <<'PY'
import json
import subprocess

slug = "local_genvex_nabto_remote"
result = subprocess.run(
    ["ha", "apps", "info", slug, "--raw-json"],
    capture_output=True, text=True, timeout=60
)
if result.returncode:
    raise SystemExit("BLOCKED: SUPERVISOR_POSTSTART")
try:
    data = json.loads(result.stdout)["data"]
    options = data["options"]
    valid = (
        data.get("version") == "0.1.0-dev5"
        and data.get("state") == "started"
        and data.get("boot") == "manual"
        and options.get("persistent_session") is True
        and options.get("poll_seconds") == 60
    )
except (ValueError, TypeError, KeyError):
    valid = False
if not valid:
    raise SystemExit("BLOCKED: SUPERVISOR_START_STATE")
print("SUPERVISOR_DEV5_STARTED: PASS")
PY

docker exec -i app_local_genvex_nabto_remote python3 - <<'PY'
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

root = Path("/opt/genvex-remote/runtime")
known = {
    "polling_service.py": "039d108d22463ab73e9d65860a6c5383905d9d09",
    "snapshot_state.py": "d1d5abe94318fcc7792e762b52805df854051e45",
    "persistent_rpc45_worker.py": "0400c2c41fce3e8c563a8c30d913472fd75a558c",
}
for name, expected in known.items():
    contents = (root / name).read_bytes()
    digest = hashlib.sha1(
        b"blob " + str(len(contents)).encode("ascii") + bytes([0]) + contents
    ).hexdigest()
    if digest != expected:
        raise SystemExit("BLOCKED: RUNTIME_IMAGE_PARITY " + name)
print("DEV5_DIAGNOSTIC_IMAGE_PARITY: PASS")

# Keep private configuration and token in process memory; never print either.
config = json.loads(Path("/data/options.json").read_text())
if config.get("persistent_session") is not True or config.get("poll_seconds") != 60:
    raise SystemExit("BLOCKED: LIVE_PERSISTENT_OPTIONS")
token = config.get("ipc_token")
if type(token) is not str or not 40 <= len(token) <= 128:
    raise SystemExit("BLOCKED: LIVE_IPC_TOKEN")

required = {"supply_air", "outdoor_air", "exhaust_air", "extract_air", "humidity"}
http_success = False
last_status = "NOT_READY"
age = None
attempts = 0

# Wait for one normal first SDK poll; do not trigger any additional RPC calls.
for attempt in range(1, 26):
    attempts = attempt
    req = urllib.request.Request(
        "http://127.0.0.1:18275/v1/snapshot",
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            raw = response.read(4097)
            if response.status != 200 or len(raw) > 4096:
                last_status = "UNEXPECTED_HTTP_OR_SIZE"
            else:
                snapshot = json.loads(raw)
                readings = snapshot.get("values")
                if (snapshot.get("schema_version") != 1
                        or snapshot.get("health") != "ok"
                        or type(readings) is not dict
                        or set(readings) != required
                        or not all(type(v) in (int, float) for v in readings.values())):
                    last_status = "INVALID_SCHEMA"
                else:
                    timestamp = datetime.fromisoformat(
                        snapshot["timestamp_utc"].replace("Z", "+00:00")
                    )
                    age = (datetime.now(timezone.utc)
                           - timestamp.astimezone(timezone.utc)).total_seconds()
                    if -3 <= age <= 180:
                        http_success = True
                        last_status = "200"
                        break
                    last_status = "STALE_SNAPSHOT"
    except urllib.error.HTTPError as exc:
        last_status = str(exc.code) if exc.code in (401, 403, 404, 503) else "HTTP_ERROR"
    except (urllib.error.URLError, TimeoutError):
        last_status = "NOT_READY"
    except (ValueError, KeyError, TypeError, OverflowError):
        last_status = "BAD_RESPONSE"
    time.sleep(5)

print("IPC_ATTEMPTS:", attempts)
print("IPC_HTTP_STATUS:", last_status)
print("IPC_V1_VALUES:", 5 if http_success else 0)
if age is not None:
    print("SNAPSHOT_AGE_SECONDS:", round(age, 1))

def workers():
    matched = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            commandline = (proc / "cmdline").read_bytes()
            if b"persistent_rpc45_worker.py" in commandline:
                matched.append(proc.name)
        except OSError:
            continue
    return matched

processes = workers()
print("PERSISTENT_WORKER_COUNT:", len(processes))
if not http_success or len(processes) != 1:
    raise SystemExit("DEV5_LIVE_RESULT: BLOCKED")
print("DEV5_LIVE_RESULT: PASS")
PY

python3 - <<'PY'
import json
from pathlib import Path

home = Path("/mnt/data/supervisor/homeassistant/.storage")
try:
    entries = json.loads((home / "core.config_entries").read_text())["data"]["entries"]
    registry = json.loads((home / "core.entity_registry").read_text())["data"]["entities"]
    configured = [e for e in entries if e.get("domain") == "genvex_remote"
                  and e.get("disabled_by") is None]
    entities = [e for e in registry if e.get("platform") == "genvex_remote"
                and e.get("entity_id")]
    if len(configured) != 1 or len(entities) != 6:
        raise ValueError()
except (OSError, ValueError, KeyError, TypeError):
    raise SystemExit("HA_REGISTRY: BLOCKED")
print("HA_CONFIG_ENTRIES:", len(configured))
print("HA_REGISTERED_ENTITIES:", len(entities))
print("HA_REGISTRY: PASS")
PY
echo "===== DEV5 RECENT RPC45 METADATA ====="
docker logs --since 5m app_local_genvex_nabto_remote 2>&1 |
  grep -E '^RPC45 [0-9]{4}-|^RPC45_DIAGNOSTIC rpc_status=' |
  tail -8 || true
echo "===== COMPLETE ====="
REMOTE
}

if run >"$OUT" 2>&1; then RC=0; else RC=$?; fi
printf '\033[3J\033[2J\033[H'
cat "$OUT"
echo "STEAM_DECK_EXIT_CODE: $RC"
exit "$RC"
