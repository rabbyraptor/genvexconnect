#!/usr/bin/env bash
# DEV3 opt-in persistent Nabto read-only live smoke, run from an SSH client.
# Usage: bash run_haos_persistent_gate_from_deck.sh root@haos-host 22222
# A pinned source revision is staged into the already running DEV3 App's /tmp;
# the App's active runtime/config and Home Assistant are not reconfigured.
set -euo pipefail
umask 077

if [[ $# -ne 2 || ! "$2" =~ ^[0-9]{1,5}$ || -z "$1" ]]; then
  echo "Usage: bash $0 SSH_USER_AT_HOST SSH_PORT" >&2
  exit 2
fi
TARGET="$1"
PORT="$2"
APP="app_local_genvex_nabto_remote"
COMMIT="29cfc151faeb048dfd2401460b32e02fed2db851"
BASE="https://raw.githubusercontent.com/rabbyraptor/genvexconnect/$COMMIT/genvex-nabto-remote/runtime"
WORK="$(mktemp -d /tmp/genvex-persistent-gate.XXXXXX)"
OUT="$WORK/result.txt"
REMOTE_DIR=""

ssh_cmd() {
  ssh -T -p "$PORT" -o BatchMode=yes -o ServerAliveInterval=30 "$TARGET" "$@"
}

cleanup() {
  if [[ -n "$REMOTE_DIR" ]]; then
    ssh_cmd "docker exec $APP rm -rf -- '$REMOTE_DIR'" >/dev/null 2>&1 || true
  fi
  rm -rf "$WORK"
}
trap cleanup EXIT

run() {
  echo "===== DEV3 PERSISTENT SDK GATE ====="
  echo "SOURCE_COMMIT: $COMMIT"
  for name in persistent_rpc45_worker.py persistent_sdk_adapter.py persistent_live_gate.py; do
    curl --fail --silent --show-error --location --max-time 45 \
      "$BASE/$name" -o "$WORK/$name" || return $?
    python3 -m py_compile "$WORK/$name" || return $?
  done
  echo "SOURCE_COMPILE: PASS"
  test "$(ssh_cmd "docker inspect '$APP' --format '{{.State.Running}}'")" = "true" || return $?
  echo "APP_RUNNING: PASS"

  REMOTE_DIR="$(ssh_cmd "docker exec '$APP' mktemp -d /tmp/genvex-persistent-live.XXXXXX")" || return $?
  if [[ ! "$REMOTE_DIR" =~ ^/tmp/genvex-persistent-live\.[A-Za-z0-9]+$ ]]; then
    echo "BLOCKED: UNEXPECTED_STAGING_DIRECTORY"
    exit 2
  fi
  for name in persistent_rpc45_worker.py persistent_sdk_adapter.py persistent_live_gate.py; do
    ssh_cmd "docker exec -i '$APP' sh -c 'umask 077; cat > $REMOTE_DIR/$name'" \
      <"$WORK/$name" || return $?
  done
  echo "TRIAL_STAGED: PASS"

  ssh_cmd "docker exec -i '$APP' python3 '$REMOTE_DIR/persistent_live_gate.py' --run-live" || return $?
}

set +e
run >"$OUT" 2>&1
CODE=$?
set -e
clear
echo "===== DEV3 PERSISTENT SDK LIVE TEST RESULT ====="
cat "$OUT"
echo "PERSISTENT_GATE_EXIT_CODE: $CODE"
exit "$CODE"
