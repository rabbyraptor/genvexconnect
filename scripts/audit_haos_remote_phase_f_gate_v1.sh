#!/bin/sh
# Read-only gate between synthetic acceptance and credentialed remote work.
# Do not print Supervisor options, profiles, credentials or tokens.
set -eu
umask 077
case "${1:---preflight}" in
  --preflight)
    [ "$#" -eq 1 ] || exit 2
    echo "===== REMOTE PHASE F PREFLIGHT ====="
    echo "Read-only: inspect App lifecycle and Docker isolation, no RPC."
    echo "PASS: inert preflight"
    exit 0 ;;
  --execute-readonly) [ "$#" -eq 1 ] || exit 2 ;;
  *) echo "Usage: sh audit_haos_remote_phase_f_gate_v1.sh --preflight|--execute-readonly" >&2; exit 2 ;;
esac

echo "===== REMOTE PHASE F READ-ONLY GATE ====="
# The CLI is known to emit YAML-like text on this host. Never use --raw
# or print its unfiltered response (it may include secret option values).
# Explicit /dev/null prevents 'ha' from eating a streamed sh -s script.
if ! command -v ha >/dev/null 2>&1; then
  echo "BLOCKED: Supervisor CLI unavailable"
  exit 1
fi
INFO=$(ha apps info local_genvex_nabto_remote </dev/null 2>/dev/null) || {
  echo "BLOCKED: Supervisor App info unavailable"
  exit 1
}
# Exact top-level scalar fields only; nested 'name:' under options is ignored.
STATE=$(printf '%s\n' "$INFO" | sed -n 's/^state: *//p' | head -n 1)
BOOT=$(printf '%s\n' "$INFO" | sed -n 's/^boot: *//p' | head -n 1)
VERSION=$(printf '%s\n' "$INFO" | sed -n 's/^version: *//p' | head -n 1)
case "$STATE" in
  stopped) echo "PASS: Supervisor App stopped" ;;
  started) echo "BLOCKED: remote App is still running; stop it manually before proceeding"; exit 1 ;;
  *) echo "BLOCKED: Supervisor App state not confirmed stopped"; exit 1 ;;
esac
case "$BOOT" in
  manual) echo "PASS: Supervisor boot is manual" ;;
  *) echo "BLOCKED: unexpected App boot mode"; exit 1 ;;
esac
case "$VERSION" in
  0.1.0-dev1) echo "PASS: expected installed App version" ;;
  *) echo "BLOCKED: App version mismatch"; exit 1 ;;
esac

if docker inspect --type container app_local_genvex_nabto_remote >/dev/null 2>&1; then
  RUNNING=$(docker inspect --type container app_local_genvex_nabto_remote --format '{{.State.Running}}')
  MODE=$(docker inspect --type container app_local_genvex_nabto_remote --format '{{.HostConfig.NetworkMode}}')
  BINDINGS=$(docker inspect --type container app_local_genvex_nabto_remote --format '{{json .HostConfig.PortBindings}}')
  [ "$RUNNING" = false ] || { echo "BLOCKED: Docker App still running"; exit 1; }
  [ "$MODE" != host ] || { echo "BLOCKED: host-networked remote App"; exit 1; }
  case "$BINDINGS" in
    '{}'|null|'') : ;;
    *) echo "BLOCKED: remote App has published ports"; exit 1 ;;
  esac
  echo "PASS: stopped Docker container isolated, no published ports"
else
  echo "PASS: no remote App Docker container present (Supervisor confirms stopped)"
fi
echo "PASS: no credentials, profiles, tokens or Nabto RPC inspected"
echo "===== REMOTE PHASE F GATE COMPLETE ====="
