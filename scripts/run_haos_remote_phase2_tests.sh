#!/bin/sh
# Phase-two acceptance: offline Python tests + disposable internal-only Docker
# network demo. No real SDK remote access, profiles or enrollment credentials.
set -eu
umask 077
ROOT=$(mktemp -d /tmp/genvex-phase2.XXXXXX)
trap 'rm -rf "$ROOT"' EXIT HUP INT TERM

BASE='https://raw.githubusercontent.com/rabbyraptor/genvexconnect/remote-nabto-connection/scripts'
curl -fsSL --max-time 45 "$BASE/run_haos_remote_dev_tests.sh" -o "$ROOT/offline.sh"
curl -fsSL --max-time 45 "$BASE/run_haos_ipc_two_container_test.sh" -o "$ROOT/ipc.sh"
echo "===== PHASE 2: NATIVE OFFLINE PYTHON ====="
sh "$ROOT/offline.sh"
echo
echo "===== PHASE 2: PRIVATE TWO-CONTAINER IPC ====="
sh "$ROOT/ipc.sh"
echo
echo "===== PHASE 2 COMPLETE ====="
