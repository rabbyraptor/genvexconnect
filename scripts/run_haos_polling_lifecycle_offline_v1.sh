#!/bin/sh
# Isolated native ARM64 HAOS test of source-only polling and worker->API contracts.
# No Nabto credentials, no live RPC, no Docker networking changes.
set -eu
umask 077
APP=app_local_genvex_nabto_runtime_test
TMP=$(mktemp -d /tmp/genvex-poller-check.XXXXXX)
STAGE=""
cleanup() {
  if [ -n "$STAGE" ]; then
    docker exec "$APP" rm -rf "$STAGE" >/dev/null 2>&1 || true
  fi
  rm -rf "$TMP"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
echo "===== GENVEX POLLING LIFECYCLE OFFLINE VALIDATION v1 ====="
test "$(docker inspect "$APP" --format '{{.State.Status}}')" = running
curl -fsSL --max-time 60 \
  'https://codeload.github.com/rabbyraptor/genvexconnect/tar.gz/aeacb550803b5f6bc3cd569ac5b48fadbe0c0360' \
  -o "$TMP/source.tar.gz"
tar -xzf "$TMP/source.tar.gz" -C "$TMP"
SRC=$(find "$TMP" -type d -path '*/experimental/genvex_remote' -print -quit)
test -f "$SRC/test_polling_service.py"
test -f "$SRC/test_worker_api_contract.py"
STAGE=$(docker exec "$APP" mktemp -d /tmp/genvex-poller-offline.XXXXXX)
tar -C "$SRC" -cf - . | docker exec -i "$APP" tar -xf - -C "$STAGE"
echo "Run all backend tests including the new polling service / API contract..."
docker exec "$APP" sh -c 'cd "$1" && python3 -m unittest discover -s . -p "test_*.py" -v' sh "$STAGE"
echo "PASS: all native ARM64 backend offline tests completed"
echo "Compile new poller and data handler..."
docker exec "$APP" python3 -m compileall -q "$STAGE"
echo "===== POLLING LIFECYCLE VALIDATION COMPLETE ====="
