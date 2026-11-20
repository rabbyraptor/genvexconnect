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

echo "===== GENVEX TWO LIVE SERIAL RPC45 POLLS v1 ====="
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
  printf "Existing Nabto SDK user / profile identity (often email): " >/dev/tty
  IFS= read -r IDENTITY </dev/tty
fi
[ -n "$IDENTITY" ] && [ "${#IDENTITY}" -le 254 ] || { echo "Invalid Nabto user" >&2; exit 2; }
case "$IDENTITY" in *[!a-zA-Z0-9@._+-]*) echo "Invalid identity characters" >&2; exit 2;; esac
HOST="${DEVICE_ID}.remote.lscontrol.dk"

echo "Downloading pinned development source..."
curl -fsSL --max-time 60 \
  'https://codeload.github.com/rabbyraptor/genvexconnect/tar.gz/e99b0d46d7ecd1c392d10414326c4f07e21e16db' \
  -o "$WORK/source.tar.gz"
tar -xzf "$WORK/source.tar.gz" -C "$WORK"
SRC=$(find "$WORK" -type d -path '*/experimental/genvex_remote' -print -quit)
test -f "$SRC/probe_remote_snapshot.py"
test -f "$SRC/ipc_live_once_server.py"
test -f "$SRC/ipc_live_once_client.py"
test -f "$SRC/live_polling_twice.py"
test -f "$SRC/sdk_snapshot_adapter.py"

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
echo "The remaining input is the password that unlocks the EXISTING encrypted Nabto private key."

# Only the RPC test server receives the existing encrypted certificate/key.
docker exec "$SERVER" mkdir -m 700 /tmp/genvex-profile
tar -C "$PROFILE" -cf - client.crt client-encrypted.key |
  docker exec -i "$SERVER" tar -xf - -C /tmp/genvex-profile
docker exec "$SERVER" chmod 600 /tmp/genvex-profile/client.crt /tmp/genvex-profile/client-encrypted.key

# A pasted HAOS command can leave a newline queued in /dev/tty,
# which the first read consumes as an empty passphrase. Retry safely.
# Keep the prompt on a separate, visible line; never echo the secret.
ATTEMPT=1
while [ "$ATTEMPT" -le 3 ]; do
  printf '\n' >/dev/tty
  printf 'Nabto private-key unlock passphrase (input hidden):\n' >/dev/tty
  printf 'Type the passphrase now, then press Enter. No characters will appear.\n' >/dev/tty
  TERM_STATE=$(stty -g </dev/tty)
  stty -echo </dev/tty
  if ! IFS= read -r PASS </dev/tty; then
    stty "$TERM_STATE" </dev/tty
    TERM_STATE=""
    printf '\n' >/dev/tty
    echo "Input cancelled" >&2
    exit 3
  fi
  stty "$TERM_STATE" </dev/tty
  TERM_STATE=""
  printf '\n' >/dev/tty
  if [ -n "$PASS" ]; then
    break
  fi
  ATTEMPT=$((ATTEMPT + 1))
  if [ "$ATTEMPT" -le 3 ]; then
    echo "No passphrase was received. Trying the hidden prompt again..." >&2
  fi
done
[ -n "$PASS" ] || { echo "No passphrase received after three prompts." >&2; exit 3; }

echo "Starting TWO serial read-only SDK polls, five seconds apart..."
# Native ARM64 Python starts each QEMU RPC45 subprocess through the tested
# SDKSnapshotAdapter; identity and unlock secret travel only via stdin.
# Suppress diagnostic errors so private SDK data is never printed.
if ! {
  printf '%s\n' "$DEVICE_ID"
  printf '%s\n' "$IDENTITY"
  printf '%s\n' "$PASS"
} | docker exec -i -e PYTHONPATH=/tmp/genvex-live "$SERVER" \
    timeout -k 5s 220s python3 -u /tmp/genvex-live/live_polling_twice.py; then
  PASS=""
  echo "FAIL: two serial live SDK polls were not both validated." >&2
  exit 4
fi
PASS=""
echo "===== PASS: TWO SERIAL REAL NABTO RPC45 POLLS ====="
echo "No write RPC, vendor enrollment, persistent service or installed App changes."
