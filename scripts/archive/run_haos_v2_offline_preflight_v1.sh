#!/bin/sh
# V2 source-only HAOS ARM64 preflight; does not open Nabto or read credentials.
# Source revision is pinned; no branch-head or raw-file caching ambiguity.
set -eu
umask 077

PINNED_SHA="640125954c0683e13372f3317e5cb9bd0a4e39ac"
APP="app_local_genvex_nabto_runtime_test"

usage() {
  printf '%s\n' "Usage: $0 --preflight | --execute-offline" >&2
  exit 2
}

[ "$#" -eq 1 ] || usage
case "$1" in
  --preflight)
    printf '%s\n' "===== GENVEX V2 HAOS OFFLINE PREFLIGHT v1 ====="
    printf '%s\n' "Pinned source: $PINNED_SHA"
    printf '%s\n' "Backend: seven-address state + v1/v2 HTTP bridge tests"
    printf '%s\n' "HA scaffold: v1 and v2 parser/transport tests"
    printf '%s\n' "No SDK, credential access, device RPC, App install or Core changes."
    printf '%s\n' "PASS: offline preview only; no container/network operations."
    exit 0
    ;;
  --execute-offline) ;;
  *) usage ;;
esac

WORK=""
STAGE=""
cleanup() {
  if [ -n "$STAGE" ]; then
    docker exec "$APP" rm -rf "$STAGE" >/dev/null 2>&1 || true
  fi
  if [ -n "$WORK" ]; then
    rm -rf "$WORK"
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

printf '%s\n' "===== GENVEX V2 HAOS ARM64 SOURCE-ONLY TEST ====="
printf '%s\n' "Pinned source: $PINNED_SHA"
test "$(docker inspect "$APP" --format '{{.State.Status}}')" = running
WORK=$(mktemp -d /tmp/genvex-haos-v2-offline.XXXXXX)
curl -fsSL --max-time 60 \
  "https://codeload.github.com/rabbyraptor/genvexconnect/tar.gz/$PINNED_SHA" \
  -o "$WORK/source.tar.gz"
tar -xzf "$WORK/source.tar.gz" -C "$WORK"
SRC=$(find "$WORK" -type d -path '*/experimental/genvex_remote' -print -quit)
HATEST=$(find "$WORK" -type d -path '*/experimental/home_assistant/tests' -print -quit)
HA=$(find "$WORK" -type d -path '*/experimental/home_assistant/custom_components/genvex_remote' -print -quit)
test -f "$SRC/test_v2_polling_state.py"
test -f "$SRC/test_v2_snapshot_bridge.py"
test -f "$SRC/v2_snapshot_bridge.py"
test -f "$HATEST/test_runtime_client_v2_draft.py"
test -f "$HA/snapshot_v2_draft.py"

STAGE=$(docker exec "$APP" mktemp -d /tmp/genvex-v2-test.XXXXXX)
docker exec "$APP" mkdir -p "$STAGE/backend" "$STAGE/ha/tests" "$STAGE/ha/custom_components/genvex_remote"
tar -C "$SRC" -cf - . | docker exec -i "$APP" tar -xf - -C "$STAGE/backend"
tar -C "$HATEST" -cf - . | docker exec -i "$APP" tar -xf - -C "$STAGE/ha/tests"
tar -C "$HA" -cf - . | docker exec -i "$APP" tar -xf - -C "$STAGE/ha/custom_components/genvex_remote"

printf '%s\n' "Running complete backend tests on isolated HAOS ARM64 test App..."
docker exec "$APP" sh -c 'cd "$1/backend" && python3 -m unittest discover -s . -p "test_*.py" -v' sh "$STAGE"
printf '%s\n' "Running isolated Home Assistant snapshot/reader tests..."
docker exec "$APP" sh -c 'cd "$1/ha/tests" && python3 -m unittest discover -s . -p "test_*.py" -v' sh "$STAGE"
printf '%s\n' "Checking Python compilation and source layout..."
docker exec "$APP" python3 -m compileall -q "$STAGE/backend" "$STAGE/ha"
printf '%s\n' "===== PASS: GENVEX V2 HAOS SOURCE-ONLY TEST ====="
printf '%s\n' "No live RPC, credentials, installed App or Core component changed."
