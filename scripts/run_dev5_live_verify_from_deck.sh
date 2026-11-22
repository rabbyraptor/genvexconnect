#!/usr/bin/env bash
# DEV5 live verification after first start. OBSERVATION ONLY; does not start App.
# Separate SSH sessions protect the script payload from Supervisor stdin reads.
set -euo pipefail
umask 077

OUT=$(mktemp)
trap 'rm -f -- "$OUT"' EXIT
HOST="root@rabbyshome.duckdns.org"

run() {
  echo "===== DEV5 LIVE VERIFY (NO RESTART) ====="

  # 1. Supervisor/HA host inspection. The only SSH input is this Python script.
  ssh -T -p 22222 -o BatchMode=yes "$HOST" 'python3 -' <<'HOST_PY'
from pathlib import Path
import json
import subprocess

app = "local_genvex_nabto_remote"
p = subprocess.run(
    ["ha", "apps", "info", app, "--raw-json"],
    stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
)
if p.returncode:
    raise SystemExit("BLOCKED: SUPERVISOR_INFO")
try:
    detail = json.loads(p.stdout)["data"]
    options = detail["options"]
    assert detail["version"] == "0.1.0-dev5"
    assert detail["state"] == "started"
    assert detail["boot"] == "manual"
    assert type(options) is dict
    assert options["persistent_session"] is True
    assert options["poll_seconds"] == 60
except (ValueError, KeyError, TypeError, AssertionError):
    raise SystemExit("BLOCKED: SUPERVISOR_STATE")
print("SUPERVISOR_DEV5_RUNNING: PASS", flush=True)

p = subprocess.run(
    ["docker", "inspect", "app_local_genvex_nabto_remote",
     "--format", "{{json .}}"],
    stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=45,
)
if p.returncode:
    raise SystemExit("BLOCKED: DOCKER_INSPECT")
try:
    state = json.loads(p.stdout)["State"]
    assert state["Running"] is True
except (ValueError, KeyError, TypeError, AssertionError):
    raise SystemExit("BLOCKED: APP_CONTAINER_STATE")
print("DEV5_CONTAINER_RUNNING: PASS", flush=True)

root = Path("/mnt/data/supervisor/homeassistant/.storage")
try:
    entries = json.loads((root / "core.config_entries").read_text())["data"]["entries"]
    entities = json.loads((root / "core.entity_registry").read_text())["data"]["entities"]
    active = [e for e in entries if e.get("domain") == "genvex_remote"
              and e.get("disabled_by") is None]
    registered = {e["entity_id"] for e in entities
                  if e.get("platform") == "genvex_remote"
                  and type(e.get("entity_id")) is str}
    if len(active) != 1 or len(registered) != 6:
        raise ValueError
except (OSError, ValueError, KeyError, TypeError):
    raise SystemExit("BLOCKED: HA_ENTITY_REGISTRY")
print("HA_CONFIG_ENTRIES: 1")
print("HA_REGISTERED_ENTITIES: 6")
print("HA_REGISTRY: PASS", flush=True)
HOST_PY

  # 2. App IPC and SDK process inspection, independent SSH stdin.
  ssh -T -p 22222 -o BatchMode=yes "$HOST" \
    'docker exec -i app_local_genvex_nabto_remote python3 -' <<'APP_PY'
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import time
import urllib.error
import urllib.request

root = Path("/opt/genvex-remote/runtime")
expected = {
    "polling_service.py": "039d108d22463ab73e9d65860a6c5383905d9d09",
    "snapshot_state.py": "d1d5abe94318fcc7792e762b52805df854051e45",
    "persistent_rpc45_worker.py": "0400c2c41fce3e8c563a8c30d913472fd75a558c",
}
try:
    for name, digest in expected.items():
        data = (root / name).read_bytes()
        sha = hashlib.sha1(
            b"blob " + str(len(data)).encode("ascii") + bytes([0]) + data
        ).hexdigest()
        if sha != digest:
            raise ValueError
except (OSError, ValueError):
    raise SystemExit("BLOCKED: DIAGNOSTIC_IMAGE_PARITY")
print("DEV5_DIAGNOSTIC_IMAGE_PARITY: PASS", flush=True)

try:
    options = json.loads(Path("/data/options.json").read_text())
    assert options["persistent_session"] is True
    assert options["poll_seconds"] == 60
    token = options["ipc_token"]
    assert type(token) is str and 40 <= len(token) <= 128
except (OSError, ValueError, KeyError, AssertionError):
    raise SystemExit("BLOCKED: APP_RUNTIME_OPTIONS")
print("DEV5_RUNTIME_OPTIONS: PASS", flush=True)

required = {"supply_air", "outdoor_air", "exhaust_air", "extract_air", "humidity"}
last_status, age, success = "NOT_READY", None, False
attempts = 0
# Observe the normal scheduled poll only. Allow for startup or a transient
# Nabto status 26; do not invoke the SDK directly or add an extra poll.
for attempt in range(1, 25):
    attempts = attempt
    req = urllib.request.Request(
        "http://127.0.0.1:18275/v1/snapshot",
        headers={"Authorization": "Bearer " + token},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            blob = response.read(4097)
            if response.status != 200 or len(blob) > 4096:
                last_status = "INVALID_HTTP_OR_SIZE"
                continue
            snapshot = json.loads(blob)
            values = snapshot.get("values")
            if (snapshot.get("schema_version") != 1
                    or snapshot.get("health") != "ok"
                    or type(values) is not dict
                    or set(values) != required
                    or not all(type(v) in (int, float) for v in values.values())):
                last_status = "INVALID_V1"
                continue
            stamp = datetime.fromisoformat(
                snapshot["timestamp_utc"].replace("Z", "+00:00")
            )
            age = (datetime.now(timezone.utc)
                   - stamp.astimezone(timezone.utc)).total_seconds()
            if -3 <= age <= 180:
                last_status = "200"
                success = True
                break
            last_status = "STALE"
    except urllib.error.HTTPError as exc:
        last_status = str(exc.code) if exc.code in (401, 403, 503) else "HTTP_ERROR"
    except (urllib.error.URLError, TimeoutError):
        last_status = "NOT_READY"
    except (KeyError, TypeError, ValueError, OverflowError):
        last_status = "INVALID_RESPONSE"
    time.sleep(5)

print("IPC_ATTEMPTS:", attempts)
print("IPC_HTTP_STATUS:", last_status)
print("IPC_V1_VALUES:", len(required) if success else 0)
if age is not None:
    print("SNAPSHOT_AGE_SECONDS:", round(age, 1))

worker_pids = []
for proc in Path("/proc").iterdir():
    if not proc.name.isdigit():
        continue
    try:
        if b"persistent_rpc45_worker.py" in (proc / "cmdline").read_bytes():
            worker_pids.append(proc.name)
    except OSError:
        pass
print("PERSISTENT_WORKER_COUNT:", len(worker_pids))
if not success or len(worker_pids) != 1:
    raise SystemExit("DEV5_IPC_RESULT: BLOCKED")
print("DEV5_IPC_RESULT: PASS", flush=True)
APP_PY

  # 3. Sanitized diagnostics only; a third independent SSH session.
  echo "===== RECENT RPC45 METADATA ====="
  ssh -T -p 22222 -o BatchMode=yes "$HOST" \
    'docker logs --since 15m app_local_genvex_nabto_remote 2>&1 | grep -E "^RPC45 [0-9]{4}-|^RPC45_DIAGNOSTIC rpc_status=" | tail -12 || true' \
    </dev/null
  echo "DEV5_RUNTIME_VERIFY: PASS"
  echo "===== COMPLETE ====="
}

if run >"$OUT" 2>&1; then
  CODE=0
else
  CODE=$?
fi
# Never let truncated remote stdin or early remote success yield a false PASS.
if [[ "$CODE" -eq 0 ]]; then
  for marker in \
    "SUPERVISOR_DEV5_RUNNING: PASS" \
    "DEV5_CONTAINER_RUNNING: PASS" \
    "HA_REGISTRY: PASS" \
    "DEV5_DIAGNOSTIC_IMAGE_PARITY: PASS" \
    "DEV5_IPC_RESULT: PASS" \
    "DEV5_RUNTIME_VERIFY: PASS" \
    "===== COMPLETE ====="; do
    if ! grep -Fqx -- "$marker" "$OUT"; then
      CODE=3
      echo "BLOCKED: INCOMPLETE_LIVE_GATE" >> "$OUT"
      break
    fi
  done
fi
printf '\033[3J\033[2J\033[H'
cat "$OUT"
echo "STEAM_DECK_EXIT_CODE: $CODE"
exit "$CODE"
