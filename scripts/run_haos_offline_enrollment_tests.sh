#!/bin/sh
# Run development-only offline tests in the existing HAOS Nabto runtime App.
# Does NOT read or touch the real profile; no vendor requests or Nabto RPCs.
set -eu
umask 077
CONTAINER=app_local_genvex_nabto_runtime_test
ROOT=$(mktemp -d /tmp/genvex-offline-host.XXXXXX)
DEST=
cleanup() {
  if [ -n "$DEST" ]; then
    docker exec "$CONTAINER" rm -rf "$DEST" >/dev/null 2>&1 || true
  fi
  rm -rf "$ROOT"
}
trap cleanup EXIT HUP INT TERM

echo "===== GENVEX HAOS NATIVE PYTHON OFFLINE TESTS ====="
docker inspect "$CONTAINER" --format '{{.State.Status}}' | grep -qx running
curl -fsSL --max-time 60 'https://codeload.github.com/rabbyraptor/genvexconnect/tar.gz/refs/heads/remote-nabto-connection' -o "$ROOT/source.tar.gz"
tar -xzf "$ROOT/source.tar.gz" -C "$ROOT"
SRC=$(find "$ROOT" -type d -path '*/experimental/genvex_remote' -print -quit)
test -n "$SRC"
DEST=$(docker exec "$CONTAINER" mktemp -d /tmp/genvex-offline.XXXXXX)
# docker cp copies the directory contents only, never the existing HAOS profile.
docker cp "$SRC/." "$CONTAINER:$DEST/"
echo "Running isolated offline tests (fake account + fake CA only)..."
docker exec "$CONTAINER" sh -c 'cd "$1" && python3 -m unittest discover -s . -p "test_*.py" -v' sh "$DEST"
echo "===== OFFLINE TESTS COMPLETE ====="
