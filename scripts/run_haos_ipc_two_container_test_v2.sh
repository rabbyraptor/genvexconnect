#!/bin/sh
# Nonproduction HTTP IPC handshake across TWO disposable, internal-network
# containers using fake telemetry only. No Nabto access, HA Core, or secrets.
set -eu
umask 077

APP=app_local_genvex_nabto_runtime_test
ID="$$"
SERVER="genvex-ipc-server-$ID"
CLIENT="genvex-ipc-client-$ID"
NETWORK="genvex-ipc-net-$ID"
ROOT=$(mktemp -d /tmp/genvex-ipc-test.XXXXXX)
cleanup() {
  docker rm -f "$SERVER" "$CLIENT" >/dev/null 2>&1 || true
  docker network rm "$NETWORK" >/dev/null 2>&1 || true
  rm -rf "$ROOT"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

echo "===== GENVEX TWO-CONTAINER IPC TEST v2 (FAKE DATA ONLY) ====="
echo "Copy method: tar over docker exec (no docker cp)"
test "$(docker inspect "$APP" --format '{{.State.Status}}')" = "running"
IMAGE=$(docker inspect "$APP" --format '{{.Image}}')
test -n "$IMAGE"
curl -fsSL --max-time 60 \
  'https://codeload.github.com/rabbyraptor/genvexconnect/tar.gz/6d069565b983e16e99ef7df4e4d868ce54eaa4a3' \
  -o "$ROOT/source.tar.gz"
tar -xzf "$ROOT/source.tar.gz" -C "$ROOT"
SRC=$(find "$ROOT" -type d -path '*/experimental/genvex_remote' -print -quit)
test -f "$SRC/ipc_demo_server.py"
test -f "$SRC/ipc_demo_client.py"

docker network create --driver bridge --internal "$NETWORK" >/dev/null
echo "PASS: dedicated no-internet Docker bridge created"

for role in server client; do
  if [ "$role" = server ]; then
    NAME="$SERVER"
    ALIAS=genvex-ipc-server
  else
    NAME="$CLIENT"
    ALIAS=genvex-ipc-client
  fi
  docker run -d --rm --name "$NAME" \
    --network "$NETWORK" --network-alias "$ALIAS" \
    --cap-drop ALL --security-opt no-new-privileges \
    --read-only --tmpfs /tmp:rw,nosuid,nodev,size=32m,mode=1777 \
    --entrypoint /bin/sh "$IMAGE" -c 'sleep 240' >/dev/null
  docker exec "$NAME" mkdir /tmp/genvex-ipc
  # Docker cp can reject writable tmpfs writes on a read-only container.
  # Stream a tar archive through docker exec instead.
  tar -C "$SRC" -cf - . | docker exec -i "$NAME" tar -xf - -C /tmp/genvex-ipc
  docker exec "$NAME" test -s /tmp/genvex-ipc/ipc_demo_client.py
  echo "PASS: $role scripts staged on writable tmpfs"
done

# Token created with native Python CSPRNG. It is NEVER included in a Docker
# argument, environment variable, console log, or repo file.
docker exec "$SERVER" python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > "$ROOT/token"
chmod 600 "$ROOT/token"
docker exec -i "$SERVER" sh -c 'umask 077; cat > /tmp/genvex-ipc/token' < "$ROOT/token"
docker exec -i "$CLIENT" sh -c 'umask 077; cat > /tmp/genvex-ipc/token' < "$ROOT/token"
docker exec "$SERVER" chmod 600 /tmp/genvex-ipc/token
docker exec "$CLIENT" chmod 600 /tmp/genvex-ipc/token

echo "Starting fixture server on the private bridge (no published port)..."
docker exec -d "$SERVER" python3 -u /tmp/genvex-ipc/ipc_demo_server.py \
  --bind 0.0.0.0 --port 18275 --token-file /tmp/genvex-ipc/token >/dev/null

attempt=0
while [ "$attempt" -lt 10 ]; do
  if docker exec "$CLIENT" python3 /tmp/genvex-ipc/ipc_demo_client.py \
    --url http://genvex-ipc-server:18275/v1/snapshot \
    --token-file /tmp/genvex-ipc/token > "$ROOT/output" 2>/dev/null; then
    cat "$ROOT/output"
    echo "===== PASS: ISOLATED TWO-CONTAINER TOKEN IPC ====="
    echo "No actual Genvex device, certificate, login or RPC was accessed."
    exit 0
  fi
  attempt=$((attempt + 1))
  sleep 1
done

echo "FAIL: disposable private IPC handshake did not complete" >&2
exit 1
