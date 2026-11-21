#!/bin/sh
# EXPERIMENTAL one-shot real Genvex RPC45 -> authenticated Docker HTTP snapshot.
# Runs two disposable bridge containers from the *installed* runtime image.
# Does not install/stop/update the HAOS App; no enrollment or RPC writes.
set -eu
umask 077

APP=app_local_genvex_nabto_runtime_test
PROFILE=/mnt/data/supervisor/genvex-nabto-remote-profile
RUN=$$
SERVER=genvex-live-server-$RUN
CLIENT=genvex-live-client-$RUN
NETWORK=genvex-live-net-$RUN
WORK=$(mktemp -d /tmp/genvex-live-bridge.XXXXXX)
PASS=""
TERM_STATE=""
cleanup() {
  if [ -n "$TERM_STATE" ]; then
    stty "$TERM_STATE" </dev/tty 2>/dev/null || true
  fi
  PASS=""
  docker rm -f "$SERVER" "$CLIENT" >/dev/null 2>&1 || true
  docker network rm "$NETWORK" >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

echo "===== GENVEX ONE-SHOT REAL RPC -> AUTHENTICATED IPC v1 ====="
test "$(docker inspect "$APP" --format '{{.State.Status}}')" = running
test -r "$PROFILE/client.crt" && test -r "$PROFILE/client-encrypted.key"
IMAGE=$(docker inspect "$APP" --format '{{.Image}}')
test -n "$IMAGE"

DEVICE_ID="${GENVEX_DEVICE_ID:-}"
IDENTITY="${GENVEX_NABTO_IDENTITY:-}"
if [ -z "$DEVICE_ID" ]; then
  printf "Existing Genvex device ID (12 digits): " >/dev/tty
  IFS= read -r DEVICE_ID </dev/tty
fi
case "$DEVICE_ID" in ''|*[!0-9]*) echo "Invalid device ID" >&2; exit 2;; esac
[ "${#DEVICE_ID}" -eq 12 ] || { echo "Invalid device ID length" >&2; exit 2; }
if [ -z "$IDENTITY" ]; then
  printf "Registered Nabto account email: " >/dev/tty
  IFS= read -r IDENTITY </dev/tty
fi
case "$IDENTITY" in *@*.*) ;; *) echo "Invalid account email" >&2; exit 2;; esac
case "$IDENTITY" in *[!a-zA-Z0-9@._+-]*) echo "Invalid identity characters" >&2; exit 2;; esac
HOST="${DEVICE_ID}.remote.lscontrol.dk"

echo "Downloading pinned development source..."
curl -fsSL --max-time 60 \
  'https://codeload.github.com/rabbyraptor/genvexconnect/tar.gz/f54ed1ff7f28a8753d297ce5eb1a73a28eaaeb22' \
  -o "$WORK/source.tar.gz"
tar -xzf "$WORK/source.tar.gz" -C "$WORK"
SRC=$(find "$WORK" -type d -path '*/experimental/genvex_remote' -print -quit)
test -f "$SRC/probe_remote_snapshot.py"
test -f "$SRC/ipc_live_once_server.py"
test -f "$SRC/ipc_live_once_client.py"

echo "Creating isolated test network and containers (no published ports)..."
docker network create --driver bridge "$NETWORK" >/dev/null
for role in server client; do
  if [ "$role" = server ]; then
    NAME="$SERVER"
    ALIAS=genvex-live-server
  else
    NAME="$CLIENT"
    ALIAS=genvex-live-client
  fi
  docker run -d --rm --name "$NAME" \
    --network "$NETWORK" --network-alias "$ALIAS" \
    --cap-drop ALL --security-opt no-new-privileges \
    --read-only --tmpfs /tmp:rw,nosuid,nodev,size=48m,mode=1777 \
    --entrypoint /bin/sh "$IMAGE" -c 'sleep 600' >/dev/null
  docker exec "$NAME" mkdir -m 700 /tmp/genvex-live
  tar -C "$SRC" -cf - . | docker exec -i "$NAME" tar -xf - -C /tmp/genvex-live
  docker exec "$NAME" test -s /tmp/genvex-live/snapshot_contract.py
done
echo "PASS: both disposable containers prepared"

# Only the RPC test server receives the existing encrypted certificate/key.
docker exec "$SERVER" mkdir -m 700 /tmp/genvex-profile
tar -C "$PROFILE" -cf - client.crt client-encrypted.key |
  docker exec -i "$SERVER" tar -xf - -C /tmp/genvex-profile
docker exec "$SERVER" chmod 600 /tmp/genvex-profile/client.crt /tmp/genvex-profile/client-encrypted.key

TERM_STATE=$(stty -g </dev/tty)
printf "Existing encrypted key unlock passphrase (hidden): " >/dev/tty
stty -echo </dev/tty
if ! IFS= read -r PASS </dev/tty; then
  echo "Input cancelled" >&2
  exit 3
fi
stty "$TERM_STATE" </dev/tty
TERM_STATE=""
printf '\n' >/dev/tty
[ -n "$PASS" ] || { echo "Empty passphrase" >&2; exit 3; }

echo "Running one authenticated read-only Nabto RPC45 batch..."
if ! {
  printf '%s\n' "$IDENTITY"
  printf '%s\n' "$HOST"
  printf '%s\n' "$PASS"
} | docker exec -i -e 'GENVEX_NABTO_PROFILE=/tmp/genvex-profile' "$SERVER" \
  timeout -k 5s 85s \
  /usr/local/bin/qemu-x86_64-static -L /opt/x86_64-sysroot \
  -E LD_LIBRARY_PATH=/opt/x86_64-sysroot/usr/local/lib \
  /opt/x86_64-sysroot/usr/local/bin/python3 -c '
import io, json, runpy, sys
identity = sys.stdin.readline().rstrip("\r\n")
host = sys.stdin.readline().rstrip("\r\n")
secret = sys.stdin.readline().rstrip("\r\n")
if not identity or not host or not secret:
    raise SystemExit("Missing test settings")
sys.stdin = io.StringIO(json.dumps({
    "identity": identity, "host": host, "passphrase": secret
}) + "\n")
sys.argv = ["/tmp/genvex-live/probe_remote_snapshot.py", "--settings-stdin"]
runpy.run_path("/tmp/genvex-live/probe_remote_snapshot.py", run_name="__main__")
' >"$WORK/rpc-output" 2>"$WORK/rpc-error"; then
  echo "FAIL: read-only Nabto RPC did not complete; secret output suppressed" >&2
  exit 4
fi
PASS=""
# The only machine-readable output accepted is an exactly one-line marker.
COUNT=$(grep -c '^GENVEX_READONLY_SNAPSHOT=' "$WORK/rpc-output" || true)
[ "$COUNT" -eq 1 ] || { echo "FAIL: missing or duplicate SDK snapshot marker" >&2; exit 4; }
sed -n 's/^GENVEX_READONLY_SNAPSHOT=//p' "$WORK/rpc-output" > "$WORK/snapshot.json"
chmod 600 "$WORK/snapshot.json"
# Copy only validated sensor JSON into private tmpfs; not the raw SDK log.
docker exec -i "$SERVER" sh -c 'umask 077; cat > /tmp/genvex-live/snapshot.json' < "$WORK/snapshot.json"
docker exec -e PYTHONPATH=/tmp/genvex-live "$SERVER" python3 -c '
import json
from snapshot_contract import parse_snapshot
with open("/tmp/genvex-live/snapshot.json", encoding="utf-8") as stream:
    snapshot = json.load(stream)
assert len(parse_snapshot(snapshot, expected_device_id=snapshot["device_id"])) == 5
'
echo "PASS: one real RPC45 batch became a complete fresh snapshot"

# Private, random one-run bearer token. No exposure in Docker argv/env/logs.
docker exec "$SERVER" python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > "$WORK/token"
chmod 600 "$WORK/token"
docker exec -i "$SERVER" sh -c 'umask 077; cat > /tmp/genvex-live/token' < "$WORK/token"
docker exec -i "$CLIENT" sh -c 'umask 077; cat > /tmp/genvex-live/token' < "$WORK/token"
printf '%s\n' "$DEVICE_ID" > "$WORK/device"
docker exec -i "$CLIENT" sh -c 'umask 077; cat > /tmp/genvex-live/device' < "$WORK/device"

echo "Serving ONLY this one-shot real snapshot over the private bridge..."
docker exec -d "$SERVER" python3 -u /tmp/genvex-live/ipc_live_once_server.py \
  --token-file /tmp/genvex-live/token \
  --snapshot-file /tmp/genvex-live/snapshot.json >/dev/null

COUNT=0
while [ "$COUNT" -lt 12 ]; do
  if docker exec "$CLIENT" python3 /tmp/genvex-live/ipc_live_once_client.py \
    --token-file /tmp/genvex-live/token \
    --device-file /tmp/genvex-live/device > "$WORK/client-output" 2>/dev/null; then
    cat "$WORK/client-output"
    echo "===== PASS: REAL RPC45 -> AUTHENTICATED TWO-CONTAINER HTTP ====="
    echo "No vendor enrollment, control writes, persistent API or installed App changes."
    exit 0
  fi
  COUNT=$((COUNT + 1))
  sleep 1
done
echo "FAIL: authenticated bridge HTTP did not complete; raw output suppressed" >&2
exit 5
