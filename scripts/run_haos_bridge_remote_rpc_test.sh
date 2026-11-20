#!/bin/sh
# Isolated *authenticated* read-only Nabto RPC 45 test on Docker bridge.
# This does not install, stop, update or modify the running HAOS App.
# Prompts for already-existing credentials; NO certificate issuance.
set -eu
umask 077

APP="app_local_genvex_nabto_runtime_test"
PROFILE="/mnt/data/supervisor/genvex-nabto-remote-profile"
TEST_NAME="genvex-bridge-probe-$$"
STTY_STATE=""
PASSPHRASE=""
STAGE=""

cleanup() {
  if [ -n "$STTY_STATE" ]; then
    stty "$STTY_STATE" </dev/tty 2>/dev/null || true
  fi
  PASSPHRASE=""
  docker rm -f "$TEST_NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

echo "===== GENVEX REMOTE: DOCKER BRIDGE TEST ====="
echo "The existing HAOS App and host profile remain unchanged."
test -r "$PROFILE/client.crt"
test -r "$PROFILE/client-encrypted.key"
test "$(docker inspect "$APP" --format '{{.State.Status}}')" = "running"

# Use the exact already installed image; never pull a third-party image.
IMAGE=$(docker inspect "$APP" --format '{{.Image}}')
test -n "$IMAGE"

DEVICE_ID="${GENVEX_DEVICE_ID:-}"
IDENTITY="${GENVEX_NABTO_IDENTITY:-}"
if [ -z "$DEVICE_ID" ]; then
  printf "Genvex device ID (12 digits): " >/dev/tty
  IFS= read -r DEVICE_ID </dev/tty
fi
case "$DEVICE_ID" in ''|*[!0-9]*) echo "Invalid device ID" >&2; exit 2;; esac
test "${#DEVICE_ID}" -eq 12 || { echo "Invalid device ID length" >&2; exit 2; }
if [ -z "$IDENTITY" ]; then
  printf "Existing Nabto account email: " >/dev/tty
  IFS= read -r IDENTITY </dev/tty
fi
case "$IDENTITY" in
  *@*.*) ;;
  *) echo "Invalid account email" >&2; exit 2 ;;
esac
case "$IDENTITY" in
  *[!a-zA-Z0-9@._+-]*) echo "Unsupported account identity characters" >&2; exit 2 ;;
esac
HOST="${DEVICE_ID}.remote.lscontrol.dk"

echo "Starting a temporary container with --network bridge (no host networking)"
# Network and privilege boundaries: no ports, no host mounts, no extra caps.
# A tmpfs is sufficient for the temporary copy of public certificate/key pair.
docker run -d --rm \
  --name "$TEST_NAME" \
  --network bridge \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=32m,mode=1777 \
  --entrypoint /bin/sh \
  "$IMAGE" -c 'sleep 240' >/dev/null

# The test intentionally doesn't print the device address or account identity.
echo "Checking container network and DNS..."
docker exec "$TEST_NAME" python3 -c '
import socket
socket.getaddrinfo("lscontrol.nabto.com", 443)
print("PASS: bridge DNS lookup succeeded")
'

STAGE=$(docker exec "$TEST_NAME" mktemp -d /tmp/genvex-bridge-XXXXXX)
case "$STAGE" in /tmp/genvex-bridge-*) ;; *) echo "Unexpected temp path" >&2; exit 3;; esac
# Copy only the same pre-existing profile, inside isolated tmpfs, not to /data.
tar -C "$PROFILE" -cf - client.crt client-encrypted.key |
  docker exec -i "$TEST_NAME" tar -xf - -C "$STAGE"
docker exec "$TEST_NAME" chmod 700 "$STAGE"
docker exec "$TEST_NAME" chmod 600 "$STAGE/client.crt" "$STAGE/client-encrypted.key"

STTY_STATE=$(stty -g </dev/tty)
printf "Existing encrypted key passphrase (hidden): " >/dev/tty
stty -echo </dev/tty
if ! IFS= read -r PASSPHRASE </dev/tty; then
  echo "Passphrase input cancelled" >&2
  exit 3
fi
stty "$STTY_STATE" </dev/tty
STTY_STATE=""
printf '\n' >/dev/tty
test -n "$PASSPHRASE" || { echo "Empty passphrase" >&2; exit 3; }

echo "Running exactly one authenticated read-only RPC45 five-sensor batch..."
# Inputs are piped only, never included in command arguments or environment.
# The existing probe handles SDK startup, clean shutdown and schema validation.
{
  printf '%s\n' "$IDENTITY"
  printf '%s\n' "$HOST"
  printf '%s\n' "$PASSPHRASE"
} | docker exec -i -e "GENVEX_NABTO_PROFILE=$STAGE" "$TEST_NAME" \
  timeout -k 5s 80s \
  /usr/local/bin/qemu-x86_64-static -L /opt/x86_64-sysroot \
  -E LD_LIBRARY_PATH=/opt/x86_64-sysroot/usr/local/lib \
  /opt/x86_64-sysroot/usr/local/bin/python3 -c '
import io
import json
import runpy
import sys
identity = sys.stdin.readline().rstrip("\r\n")
host = sys.stdin.readline().rstrip("\r\n")
passphrase = sys.stdin.readline().rstrip("\r\n")
if not identity or not host or not passphrase:
    raise SystemExit("Missing existing profile settings")
sys.stdin = io.StringIO(json.dumps({
    "identity": identity, "host": host, "passphrase": passphrase
}) + "\n")
sys.argv = ["/opt/nabto/probe_remote_batch.py", "--settings-stdin"]
runpy.run_path("/opt/nabto/probe_remote_batch.py", run_name="__main__")
'
PASSPHRASE=""
echo "===== PASS: AUTHENTICATED READ-ONLY BRIDGE NETWORK RPC ====="
echo "The temporary test container is removed when this script exits."
