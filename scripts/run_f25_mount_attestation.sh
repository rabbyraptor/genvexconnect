#!/bin/sh
# F2.5: HAOS-host-only diagnostic mount attestation.
# No credentials printed, no SDK RPC, no writes except Supervisor start/stop.
set -eu
APP=local_genvex_nabto_remote
CONTAINER=app_local_genvex_nabto_remote
EXPECTED=/mnt/data/supervisor/apps/data/local_genvex_nabto_remote
START_ATTEMPTED=0
cleanup() {
  if [ "$START_ATTEMPTED" -eq 1 ]; then
    echo "Stopping experimental App..."
    if ! ha apps stop "$APP" >/dev/null 2>&1; then
      echo "FAIL: stop command failed; check App state immediately"
      return 1
    fi
    state=$(ha apps info "$APP" --raw-json | jq -r '.data.state')
    if [ "$state" != stopped ]; then
      echo "FAIL: App not confirmed stopped"
      return 1
    fi
    echo "PASS: App stopped"
  fi
}
trap cleanup EXIT
echo "===== F2.5 PRECHECK ====="
command -v jq >/dev/null
command -v docker >/dev/null
command -v ha >/dev/null
info=$(ha apps info "$APP" --raw-json)
printf '%s\n' "$info" | jq -e '
  .data.state == "stopped" and
  .data.boot == "manual" and
  .data.options.diagnostic_only == true and
  .data.options.device_id == "" and
  .data.options.identity == "" and
  .data.options.unlock_secret == "" and
  .data.options.ipc_token == ""
' >/dev/null || { echo "FAIL: unsafe App configuration"; exit 1; }
[ -d "$EXPECTED" ] && [ ! -L "$EXPECTED" ] || {
  echo "FAIL: expected App data directory invalid"; exit 1;
}
for path in "$EXPECTED/profile" "$EXPECTED/ipc-token"; do
  if [ -e "$path" ] || [ -L "$path" ]; then
    echo "FAIL: credential path exists"; exit 1
  fi
done
echo "PASS: diagnostic configuration and absent credentials"
echo "===== START DIAGNOSTIC APP ====="
# Arm cleanup BEFORE attempting start: Supervisor can partially start and error.
START_ATTEMPTED=1
ha apps start "$APP" >/dev/null || { echo "FAIL: start command"; exit 1; }
echo "===== VERIFY /data MOUNT ====="
found=0
i=0
while [ "$i" -lt 10 ]; do
  if docker container inspect "$CONTAINER" >/dev/null 2>&1; then
    found=1
    break
  fi
  i=$((i + 1))
  sleep 1
done
if [ "$found" -ne 1 ]; then
  echo "FAIL: container metadata unavailable"
  exit 1
fi
actual=$(docker container inspect "$CONTAINER" |
  jq -r '.[0].Mounts[] | select(.Destination == "/data") | .Source')
if [ "$actual" != "$EXPECTED" ]; then
  echo "FAIL: /data mount mismatch"
  exit 1
fi
echo "PASS: experimental App /data mount matches Supervisor directory"
echo "===== F2.5 CHECK COMPLETE ====="
