#!/usr/bin/env bash
# Fake data only. Must run on a disposable CI Docker host, not HAOS.
set -euo pipefail

IMAGE="genvex-nabto-remote:ci"
NET="genvex-ci-private-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
SERVER="genvex-ci-ipc-server-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
HOST="fake-remote-app"
SCRIPT="/opt/genvex-remote/runtime/offline_ipc_network_smoke.py"
DIAG_DIR=""

cleanup() {
  docker rm -f "$SERVER" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
  if test -n "$DIAG_DIR"; then
    rm -rf -- "$DIAG_DIR"
  fi
}
trap cleanup EXIT

docker network create --internal --driver bridge "$NET" >/dev/null
test "$(docker network inspect "$NET" --format '{{.Internal}}')" = true

run_server() {
  local mode="$1"
  docker run -d \
    --name "$SERVER" \
    --network "$NET" --network-alias "$HOST" \
    --read-only --tmpfs /tmp:rw,nosuid,nodev,size=16m \
    --cap-drop ALL --security-opt no-new-privileges \
    --memory 256m --pids-limit 64 \
    --entrypoint python3 \
    "$IMAGE" "$SCRIPT" serve "$mode" >/dev/null

  # No ports may be published on the Docker host.
  test "$(docker inspect "$SERVER" --format '{{json .HostConfig.PortBindings}}')" = '{}'
  test -z "$(docker port "$SERVER")"
  local ready=0
  for _ in $(seq 1 30); do
    if docker logs "$SERVER" 2>&1 | grep -q 'Fake-only HTTP server ready'; then
      ready=1
      break
    fi
    if test "$(docker inspect "$SERVER" --format '{{.State.Running}}')" != true; then
      docker logs "$SERVER" 2>&1
      return 1
    fi
    sleep 1
  done
  test "$ready" = 1
}

run_client() {
  local mode="$1"
  docker run --rm \
    --network "$NET" --read-only \
    --tmpfs /tmp:rw,nosuid,nodev,size=16m \
    --cap-drop ALL --security-opt no-new-privileges \
    --memory 256m --pids-limit 64 \
    --entrypoint python3 \
    "$IMAGE" "$SCRIPT" check "$HOST" "$mode"
}

echo "===== ISOLATED IPC: AVAILABLE SNAPSHOT ====="
run_server available
run_client available
docker rm -f "$SERVER" >/dev/null

echo "===== ISOLATED IPC: UNAVAILABLE SNAPSHOT ====="
run_server unavailable
run_client unavailable

echo "===== ACTUAL APP BOOTSTRAP: DIAGNOSTIC ONLY ====="
docker rm -f "$SERVER" >/dev/null
DIAG_DIR=$(mktemp -d /tmp/genvex-ci-diagnostic.XXXXXX)
# Deliberately fake-only App options: no Nabto identity, profile, token, or key.
printf '%s\\n' '{"diagnostic_only":true,"device_id":"","identity":"","unlock_secret":"","ipc_token":"","poll_seconds":60}' > "$DIAG_DIR/options.json"
docker run -d \\
  --name "$SERVER" \\
  --network "$NET" --network-alias "$HOST" \\
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=16m \\
  --mount "type=bind,source=$DIAG_DIR,target=/data,readonly" \\
  --cap-drop ALL --security-opt no-new-privileges \\
  --memory 256m --pids-limit 64 \\
  --entrypoint python3 \\
  "$IMAGE" -u /opt/genvex-remote/runtime/app_bootstrap.py >/dev/null

test "$(docker inspect "$SERVER" --format '{{json .HostConfig.PortBindings}}')" = '{}'
test -z "$(docker port "$SERVER")"
ready=0
for _ in $(seq 1 30); do
  if docker logs "$SERVER" 2>&1 | grep -q 'DIAGNOSTIC ONLY; synthetic data, no Nabto'; then
    ready=1
    break
  fi
  if test "$(docker inspect "$SERVER" --format '{{.State.Running}}')" != true; then
    docker logs "$SERVER" 2>&1
    exit 1
  fi
  sleep 1
done
test "$ready" = 1

docker run --rm \\
  --network "$NET" --read-only \\
  --tmpfs /tmp:rw,nosuid,nodev,size=16m \\
  --cap-drop ALL --security-opt no-new-privileges \\
  --memory 256m --pids-limit 64 \\
  --entrypoint python3 \\
  "$IMAGE" "$SCRIPT" check-diagnostic "$HOST"

echo "PASS: fake-only internal Docker IPC AND actual diagnostic App startup; no host ports or Nabto connections"
