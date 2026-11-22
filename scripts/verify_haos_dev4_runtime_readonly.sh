#!/usr/bin/env bash
# Read-only DEV4 App check from Steam Deck: source, persistent session, local IPC.
# No SDK invoke, App restart, install, profile export or HTTP token disclosure.
set -euo pipefail
umask 077
OUTPUT=$(mktemp)
trap 'rm -f -- "$OUTPUT"' EXIT

if ssh -T -p 22222 root@rabbyshome.duckdns.org 'sh -s' >"$OUTPUT" 2>&1 <<'REMOTE'
set -eu
echo "===== DEV4 SOURCE AND IPC READ-ONLY GATE ====="
docker exec -i app_local_genvex_nabto_remote python3 - <<'PY'
from datetime import datetime, timezone
import ast
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request

root = Path("/opt/genvex-remote/runtime")
names = (
    "app_bootstrap.py", "polling_runtime.py", "polling_service.py",
    "snapshot_state.py", "persistent_sdk_adapter.py",
    "persistent_rpc45_worker.py", "sdk_snapshot_adapter.py",
    "polling_http_server.py", "snapshot_contract.py", "ipc_auth.py",
)
baseline = {
    "app_bootstrap.py": "acdbcfb548b7539c6e3075f49f3a074620abaa79",
    "polling_runtime.py": "2fe0d8ff39fe81d2f818415de3c0f989c94a6f8b",
    "polling_service.py": "2a5dffff25feb51a4cd108e68a47d16f7de594e7",
    "snapshot_state.py": "1726a3234931f6488f964eff2aa1c56bdac60131",
    "persistent_sdk_adapter.py": "62a2895437a1b8e6cda101d6b765b8fa30145158",
    "persistent_rpc45_worker.py": "a865fb7d59d57fed7bbbcf8c264b7ee9f71781d2",
    "sdk_snapshot_adapter.py": "2b55624e31331596135eb7dc8068a39a932760f7",
    "polling_http_server.py": "2c3533cf9674f8d7160e086e209696d75941e630",
    "snapshot_contract.py": "e276b5d21ebd646138dbaf85ebc5527ece2bc974",
    "ipc_auth.py": "78c0574f017b3987fc2e3b4ad792c040ebd4e88a",
}
match = 0
mismatch = []
for name in names:
    try:
        source = (root / name).read_bytes()
        ast.parse(source, filename=name)
        sha = hashlib.sha1(
            b"blob " + str(len(source)).encode() + bytes([0]) + source
        ).hexdigest()
    except (OSError, SyntaxError):
        print("SOURCE_SYNTAX: FAIL", name)
        raise SystemExit(2)
    if sha == baseline[name]:
        match += 1
    else:
        mismatch.append(name)
print("SOURCE_SYNTAX: PASS", len(names))
print("INSTALLED_BASELINE_MATCH:", match, "of", len(names))
print("CHANGED_FILES:", ",".join(mismatch) if mismatch else "none")

opts = Path("/data/options.json")
try:
    config = json.loads(opts.read_text())
    print("PERSISTENT_SESSION:", config.get("persistent_session"))
    print("POLL_SECONDS:", config.get("poll_seconds"))
except (OSError, ValueError, TypeError):
    print("OPTIONS: UNAVAILABLE")
    raise SystemExit(2)
worker_pids = []
for proc in Path("/proc").iterdir():
    if not proc.name.isdigit():
        continue
    try:
        argv = (proc / "cmdline").read_bytes()
        if b"persistent_rpc45_worker.py" in argv:
            worker_pids.append(proc.name)
    except OSError:
        continue
print("PERSISTENT_WORKER_COUNT:", len(worker_pids))

# Reuse the locally configured token strictly in memory. Never print it.
token = config.get("ipc_token")
if not isinstance(token, str) or not 40 <= len(token) <= 128:
    print("IPC_SNAPSHOT: NO_VALID_TOKEN")
    raise SystemExit(2)
req = urllib.request.Request(
    "http://127.0.0.1:18275/v1/snapshot",
    headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
)
try:
    with urllib.request.urlopen(req, timeout=5) as response:
        if response.status != 200:
            print("IPC_HTTP_STATUS:", response.status)
        else:
            raw = response.read(4097)
            if len(raw) > 4096:
                raise ValueError("Oversize snapshot")
            snapshot = json.loads(raw)
            values = snapshot["values"]
            required = {"supply_air", "outdoor_air", "exhaust_air", "extract_air", "humidity"}
            if (snapshot.get("schema_version") != 1
                    or snapshot.get("health") != "ok"
                    or set(values) != required):
                raise ValueError("Unexpected snapshot schema")
            ts = datetime.fromisoformat(snapshot["timestamp_utc"].replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds()
            print("IPC_HTTP_STATUS: 200")
            print("IPC_V1_VALUES:", len(values))
            print("SNAPSHOT_AGE_SECONDS:", round(age, 1))
except urllib.error.HTTPError as exc:
    print("IPC_HTTP_STATUS:", exc.code)
except (OSError, ValueError, KeyError, TypeError) as exc:
    print("IPC_SNAPSHOT_ERROR:", type(exc).__name__)
PY
echo "===== LAST RPC45 ENTRIES ====="
docker logs --since 20m app_local_genvex_nabto_remote 2>&1 |
  grep -E 'RPC45_DIAGNOSTIC|RPC45 .* (OK|FEJL) ' | tail -15 || true
echo "===== COMPLETE ====="
REMOTE
then
  CODE=0
else
  CODE=$?
fi
printf '\033[3J\033[2J\033[H'
cat "$OUTPUT"
echo "EXIT_CODE: $CODE"
exit "$CODE"
