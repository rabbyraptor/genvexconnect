#!/bin/sh
# Read-only development validation on running isolated HAOS v0.5.0 App.
# No controller RPC, account credentials, production profile or enrollment.
set -eu
umask 077
CONTAINER=app_local_genvex_nabto_runtime_test
WORK=$(mktemp -d /tmp/genvex-remote-dev.XXXXXX)
CONTAINER_DIR=
cleanup() {
  if [ -n "$CONTAINER_DIR" ]; then
    docker exec "$CONTAINER" rm -rf "$CONTAINER_DIR" >/dev/null 2>&1 || true
  fi
  rm -rf "$WORK"
}
trap cleanup EXIT HUP INT TERM

echo "===== GENVEX REMOTE HAOS OFFLINE DEV VALIDATION ====="
test "$(docker inspect "$CONTAINER" --format '{{.State.Status}}')" = "running"
curl --fail --silent --show-error --location --max-time 60 \
  'https://codeload.github.com/rabbyraptor/genvexconnect/tar.gz/refs/heads/remote-nabto-connection' \
  -o "$WORK/repo.tar.gz"
tar -xzf "$WORK/repo.tar.gz" -C "$WORK"
ROOT=$(find "$WORK" -type d -name genvex_remote -path '*/experimental/genvex_remote' -print -quit)
test -n "$ROOT"
EXPERIMENTAL=$(dirname "$ROOT")
test -f "$EXPERIMENTAL/home_assistant/tests/test_snapshot.py"
mkdir "$WORK/testfiles"
cp -R "$EXPERIMENTAL/genvex_remote" "$WORK/testfiles/genvex_remote"
cp -R "$EXPERIMENTAL/home_assistant" "$WORK/testfiles/home_assistant"
CONTAINER_DIR=$(docker exec "$CONTAINER" mktemp -d /tmp/genvex-dev.XXXXXX)
docker cp "$WORK/testfiles/." "$CONTAINER:$CONTAINER_DIR/"
echo "1. Existing certificate, profile, HTTP mock and sensor tests:"
docker exec "$CONTAINER" sh -c 'cd "$1" && python3 -m unittest discover -s genvex_remote -p "test_*.py" -v' sh "$CONTAINER_DIR"
echo "2. New Home Assistant snapshot parser and fail-closed reader tests:"
docker exec "$CONTAINER" sh -c 'cd "$1" && python3 -m unittest discover -s home_assistant/tests -p "test_*.py" -v' sh "$CONTAINER_DIR"
echo "3. Static syntax check of Home Assistant UI integration:"
docker exec "$CONTAINER" sh -c 'cd "$1" && python3 -m compileall -q home_assistant/custom_components/genvex_remote && echo "PASS: HA scaffold compiles"' sh "$CONTAINER_DIR"
echo "===== ALL OFFLINE DEV VALIDATIONS COMPLETE ====="
