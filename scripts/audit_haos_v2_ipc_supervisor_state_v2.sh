#!/bin/sh
# Read-only Supervisor/App state check v2; extracts safe fields only.
# Do NOT print raw Supervisor data: may include private App options.
set -eu
umask 077

case "${1:---preflight}" in
  --preflight)
    [ "$#" -le 1 ] || exit 2
    echo "===== GENVEX REMOTE SUPERVISOR STATE PREFLIGHT v2 ====="
    echo "Check Supervisor installed/stopped separately from Docker container."
    echo "No App start/install, no tokens, no profile reads, no RPC."
    echo "PASS: inert preflight"
    exit 0 ;;
  --execute-readonly) [ "$#" -eq 1 ] || exit 2 ;;
  *) echo "Usage: sh $0 --preflight|--execute-readonly" >&2; exit 2 ;;
esac

echo "===== GENVEX REMOTE SUPERVISOR STATE v2 (READ ONLY) ====="
if command -v ha >/dev/null 2>&1; then
  # The raw result may include App configuration: never store or display it.
  # Extract only allowlisted metadata in a pipeline.
  # IMPORTANT: this audit runs via SSH 'sh -s' where stdin is script source.\n  # Never let ha consume the rest of script; it must read /dev/null.\n  # Core has Python even if the HAOS host lacks a Python command.\n  if ha apps info local_genvex_nabto_remote --raw </dev/null 2>/dev/null |\n     docker exec -i homeassistant python3 -B -c '
import json, sys
try:
    d = json.load(sys.stdin)
    if not isinstance(d, dict):
        raise ValueError
    if isinstance(d.get("data"), dict):
        d = d["data"]
    state = d.get("state")
    installed = d.get("installed")
    version = d.get("version")
    if state not in ("started", "stopped", "unknown", "error"):
        state = "unknown"
    if type(installed) is not bool:
        installed = state in ("started", "stopped")
    if not isinstance(version, str) or not (
        0 < len(version) <= 40 and all(c.isalnum() or c in ".-_+" for c in version)
    ):
        version = "unknown"
    print("Supervisor installed:", "yes" if installed else "no")
    print("Supervisor state:", state)
    print("Supervisor version:", version)
except (ValueError, TypeError):
    print("Supervisor App metadata: unavailable")
    sys.exit(2)
'; then
    :
  else
    echo "Supervisor metadata: unavailable; no assumptions about installation"
  fi
else
  echo "Supervisor CLI: unavailable; cannot determine App installation"
fi

APP=app_local_genvex_nabto_remote
if docker inspect --type container "$APP" >/dev/null 2>&1; then
  echo "Docker dedicated App container: present"
  docker inspect --type container "$APP" --format 'Docker running={{.State.Running}} network={{.HostConfig.NetworkMode}}'
  BINDINGS=$(docker inspect --type container "$APP" --format '{{json .HostConfig.PortBindings}}')
  case "$BINDINGS" in
    "{}"|"null"|"") echo "Docker host-published ports: none" ;;
    *) echo "Docker host-published ports: PRESENT (BLOCKED for IPC)" ;;
  esac
else
  echo "Docker dedicated App container: absent (may be installed and stopped)"
fi

if docker inspect --type container app_local_genvex_nabto_runtime_test >/dev/null 2>&1; then
  MODE=$(docker inspect --type container app_local_genvex_nabto_runtime_test --format '{{.HostConfig.NetworkMode}}')
  if [ "$MODE" = "host" ]; then
    echo "QEMU test App network: host (not eligible for IPC listener)"
  else
    echo "QEMU test App network: not host (still excluded from IPC listener)"
  fi
fi
echo "===== SUPERVISOR STATE AUDIT COMPLETE v2 (NO CHANGES) ====="
