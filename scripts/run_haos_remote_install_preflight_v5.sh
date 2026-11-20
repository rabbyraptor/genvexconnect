#!/bin/sh
# No live Nabto, certificate, credentials or App configuration modifications.
set -eu
umask 077
APP=app_local_genvex_nabto_runtime_test
WORK=$(mktemp -d /tmp/genvex-install-preflight.XXXXXX)
STAGE=""
cleanup() {
  if [ -n "$STAGE" ]; then
    docker exec "$APP" rm -rf "$STAGE" >/dev/null 2>&1 || true
  fi
  rm -rf "$WORK"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

echo "===== GENVEX REMOTE INSTALL PRE-FLIGHT v5 ====="
test "$(docker inspect "$APP" --format '{{.State.Status}}')" = running
curl -fsSL --max-time 60 \
  'https://codeload.github.com/rabbyraptor/genvexconnect/tar.gz/5f4390efc8cdc68fe347032cf779c4441d4a5251' \
  -o "$WORK/source.tar.gz"
tar -xzf "$WORK/source.tar.gz" -C "$WORK"
SRC=$(find "$WORK" -type d -path '*/experimental/genvex_remote' -print -quit)
HA=$(find "$WORK" -type d -path '*/experimental/home_assistant/custom_components/genvex_remote' -print -quit)
test -f "$SRC/test_polling_runtime.py"
test -f "$SRC/polling_runtime.py"
test -f "$HA/config_flow.py"
test -f "$HA/runtime_client.py"
HATEST=$(find "$WORK" -type d -path '*/experimental/home_assistant/tests' -print -quit)
test -f "$HATEST/test_runtime_client.py"
STAGE=$(docker exec "$APP" mktemp -d /tmp/genvex-preflight.XXXXXX)
docker exec "$APP" mkdir -p "$STAGE/backend" "$STAGE/home_assistant/custom_components/genvex_remote" "$STAGE/home_assistant/tests"
tar -C "$SRC" -cf - . | docker exec -i "$APP" tar -xf - -C "$STAGE/backend"
tar -C "$HA" -cf - . | docker exec -i "$APP" tar -xf - -C "$STAGE/home_assistant/custom_components/genvex_remote"
tar -C "$HATEST" -cf - . | docker exec -i "$APP" tar -xf - -C "$STAGE/home_assistant/tests"
echo "Running backend tests, including authenticated HTTP and private config..."
docker exec "$APP" sh -c 'cd "$1/backend" && python3 -m unittest discover -s . -p "test_*.py" -v' sh "$STAGE"
echo "Running Home Assistant transport and snapshot tests (without HA Core)..." 
docker exec "$APP" sh -c 'cd "$1/home_assistant/tests" && python3 -m unittest discover -s . -p "test_*.py" -v' sh "$STAGE"
echo "Checking backend and HA integration syntax..."
docker exec "$APP" python3 -m compileall -q "$STAGE/backend" "$STAGE/home_assistant"
echo "Checking HA manifest and UI strings JSON..."
docker exec "$APP" python3 -c 'import json,sys; from pathlib import Path; p=Path(sys.argv[1]); json.loads((p/"manifest.json").read_text()); json.loads((p/"strings.json").read_text())' "$STAGE/home_assistant/custom_components/genvex_remote"
echo "===== PASS: REMOTE RUNTIME + HA SOURCE PRE-FLIGHT ====="
echo "This does NOT install or start a new App or HA integration."
