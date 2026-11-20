#!/bin/sh
# Read-only HAOS v2 IPC network topology gate. Never opens ports or starts RPCs.
# Strictly checks installed containers, not just the source YAML.
set -eu
umask 077

APP=app_local_genvex_nabto_remote
CORE=homeassistant
TEST_APP=app_local_genvex_nabto_runtime_test

if [ "${1:---preflight}" = "--preflight" ] && [ "$#" -le 1 ]; then
  echo "===== HAOS V2 IPC NETWORK GATE PREFLIGHT ====="
  echo "Inspect Core, isolated remote App and existing QEMU test App; no changes."
  echo "Remote v2 listener requires a dedicated network, NEVER host mode."
  echo "DNS lookup tests only; no HTTP, SDK, credentials or device RPC."
  echo "PASS: inert preflight"
  exit 0
fi
if [ "$#" -ne 1 ] || [ "$1" != "--execute-readonly" ]; then
  echo "Usage: sh $0 --preflight|--execute-readonly" >&2
  exit 2
fi

echo "===== HAOS V2 IPC NETWORK GATE (READ ONLY) ====="
command -v docker >/dev/null
docker inspect --type container "$CORE" >/dev/null
echo "Core container: present"

if docker inspect --type container "$TEST_APP" >/dev/null 2>&1; then
  TEST_MODE=$(docker inspect --type container "$TEST_APP" --format '{{.HostConfig.NetworkMode}}')
  echo "Existing QEMU test App network mode: $TEST_MODE"
  if [ "$TEST_MODE" = host ]; then
    echo "BLOCKED: existing QEMU test App is host-networked; never bind private v2 HTTP here."
  else
    echo "Existing QEMU test App is not host-networked; remains excluded from v2 service."
  fi
else
  echo "Existing QEMU test App not present."
fi

if ! docker inspect --type container "$APP" >/dev/null 2>&1; then
  echo "NOT READY: dedicated remote App is not installed; no bridge enabled."
  echo "===== READ-ONLY GATE COMPLETE ====="
  exit 0
fi

MODE=$(docker inspect --type container "$APP" --format '{{.HostConfig.NetworkMode}}')
PORTS=$(docker inspect --type container "$APP" --format '{{json .HostConfig.PortBindings}}')
echo "Dedicated remote App network mode: $MODE"
if [ "$MODE" = host ] || [ "$MODE" = none ] || [ "$MODE" = bridge ]; then
  echo "BLOCKED: remote App must use a separately reviewed private App network."
  exit 3
fi
case "$PORTS" in
  ""|"null"|"{}") echo "PASS: no host-published ports in bindings." ;;
  *) echo "BLOCKED: host port bindings configured."; exit 3 ;;
esac

# Core DNS lookup only; DNS resolution alone never authorizes the IPC listener.
docker exec "$CORE" python3 -B -c '
import socket
name = "local-genvex-nabto-remote"
try:
    resolved = socket.getaddrinfo(name, 18275, type=socket.SOCK_STREAM)
except (socket.gaierror, OSError):
    resolved = []
print("Core -> dedicated remote App DNS:", "RESOLVES" if resolved else "NOT_RESOLVED")
'
echo "MANUAL REVIEW REQUIRED: IP/interface isolation, route access and token provisioning."
echo "===== READ-ONLY GATE COMPLETE ====="
