#!/bin/sh
# Verify QEMU SDK snapshot subprocess adapter with FAKE subprocesses only.
# Runs inside the existing isolated HAOS runtime, without altering the App.
# No secret, SDK invocation, internet from the container, or live RPC.
set -eu
umask 077
APP=app_local_genvex_nabto_runtime_test
HOSTDIR=$(mktemp -d /tmp/genvex-adapter-test.XXXXXX)
APPDIR=""
cleanup() {
  if [ -n "$APPDIR" ]; then
    docker exec "$APP" rm -rf "$APPDIR" >/dev/null 2>&1 || true
  fi
  rm -rf "$HOSTDIR"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

echo "===== GENVEX SDK SNAPSHOT ADAPTER OFFLINE v1 ====="
test "$(docker inspect "$APP" --format '{{.State.Status}}')" = running
curl -fsSL --max-time 60 \
  'https://codeload.github.com/rabbyraptor/genvexconnect/tar.gz/4d2a69f3989ee01590487371dd9ab7b06ea96b16' \
  -o "$HOSTDIR/source.tar.gz"
tar -xzf "$HOSTDIR/source.tar.gz" -C "$HOSTDIR"
SOURCE=$(find "$HOSTDIR" -type d -path '*/experimental/genvex_remote' -print -quit)
test -f "$SOURCE/test_sdk_snapshot_adapter.py"
test -f "$SOURCE/sdk_snapshot_adapter.py"
APPDIR=$(docker exec "$APP" mktemp -d /tmp/genvex-sdk-adapter.XXXXXX)
tar -C "$SOURCE" -cf - . | docker exec -i "$APP" tar -xf - -C "$APPDIR"

echo "Running complete backend test suite including subprocess timeouts and cancellation..."
docker exec "$APP" sh -c 'cd "$1" && python3 -m unittest discover -s . -p "test_*.py" -v' sh "$APPDIR"
docker exec "$APP" python3 -m compileall -q "$APPDIR"
echo "===== PASS: SDK ADAPTER OFFLINE TESTS AND COMPILATION ====="
echo "No real device communication or certificate access occurred."
