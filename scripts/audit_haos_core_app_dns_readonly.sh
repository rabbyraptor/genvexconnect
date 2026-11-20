#!/bin/sh
# Read-only DNS lookup in the existing Home Assistant Core container.
# No network requests to app services, tokens, private files or writes.
set -eu
echo "===== HAOS CORE-TO-APP DNS READ-ONLY TEST ====="
docker inspect --type container homeassistant --format 'Core running={{.State.Running}} Network={{.HostConfig.NetworkMode}}'
docker exec homeassistant python3 -c '
import socket
names = (
    "supervisor",
    "hassio",
    "local-genvex-nabto-runtime-test",
    "app_local_genvex_nabto_runtime_test",
    "local-genvex-nabto-remote",
    "app_local_genvex_nabto_remote",
)
for name in names:
    try:
        result = socket.getaddrinfo(name, 18275, type=socket.SOCK_STREAM)
        print(name + ": RESOLVES" if result else name + ": NOT_RESOLVED")
    except (socket.gaierror, OSError):
        print(name + ": NOT_RESOLVED")
'
echo "===== DNS TEST COMPLETE (NO APP CONNECTIONS) ====="
