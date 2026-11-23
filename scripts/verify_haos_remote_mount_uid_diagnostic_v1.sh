#!/bin/sh
# Read-only mount/UID attestation while the already-installed App is running
# in confirmed synthetic DIAGNOSTIC ONLY mode. Does NOT start or stop Apps.
set -eu
umask 077

case "${1:---preflight}" in
  --preflight)
    [ "$#" -eq 1 ] || exit 2
    echo "===== REMOTE APP MOUNT / UID PREFLIGHT ====="
    echo "Requires user-started diagnostic-only App; no secrets, SDK or writes."
    echo "PASS: inert preflight"
    exit 0 ;;
  --execute-readonly) [ "$#" -eq 1 ] || exit 2 ;;
  *) echo "Usage: sh verify_haos_remote_mount_uid_diagnostic_v1.sh --preflight|--execute-readonly" >&2; exit 2 ;;
esac

echo "===== REMOTE APP MOUNT / UID ATTESTATION (READ ONLY) ====="
command -v ha >/dev/null 2>&1 || { echo "BLOCKED: ha CLI missing"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "BLOCKED: Docker missing"; exit 1; }

# Preserve only top-level status fields; never store or print options.
STATUS=$(ha apps info local_genvex_nabto_remote </dev/null 2>/dev/null |
  sed -n '/^state: /p; /^version: /p; /^boot: /p') || {
  echo "BLOCKED: Supervisor status unavailable"
  exit 1
}
STATE=$(printf '%s\n' "$STATUS" | sed -n 's/^state: *//p')
BOOT=$(printf '%s\n' "$STATUS" | sed -n 's/^boot: *//p')
VERSION=$(printf '%s\n' "$STATUS" | sed -n 's/^version: *//p')
[ "$STATE" = started ] && [ "$BOOT" = manual ] &&
  [ "$VERSION" = 0.1.0-dev1 ] || {
  echo "BLOCKED: expected manually started diagnostic App v0.1.0-dev1"
  exit 1
}
echo "PASS: expected dedicated App running (not proof of diagnostic mode)"

APP=app_local_genvex_nabto_remote
EXPECTED=/mnt/data/supervisor/apps/data/local_genvex_nabto_remote
docker inspect --type container "$APP" >/dev/null 2>&1 || {
  echo "BLOCKED: dedicated container unavailable"
  exit 1
}
MODE=$(docker inspect --type container "$APP" --format '{{.HostConfig.NetworkMode}}')
RUNNING=$(docker inspect --type container "$APP" --format '{{.State.Running}}')
PORTS=$(docker inspect --type container "$APP" --format '{{json .HostConfig.PortBindings}}')
[ "$RUNNING" = true ] && [ "$MODE" != host ] || {
  echo "BLOCKED: App must be running without host network"
  exit 1
}
case "$PORTS" in
  '{}'|null|'') : ;;
  *) echo "BLOCKED: App publishes a host port"; exit 1 ;;
esac
echo "PASS: isolated running App, no published host ports"

# Verify diagnostic mode before inspecting private-data metadata. This
# request carries no credentials, and production snapshot must remain 404.
if docker exec homeassistant python3 -B -c '
import json
import urllib.error
import urllib.request
base = "http://local-genvex-nabto-remote:18275"
try:
    with urllib.request.urlopen(base + "/v1/diagnostic", timeout=3) as response:
        raw = response.read(2049)
        if response.status != 200 or len(raw) > 2048:
            raise ValueError
        doc = json.loads(raw)
        if (doc.get("mode") != "DIAGNOSTIC_ONLY"
                or doc.get("synthetic") is not True
                or doc.get("notice") != "NOT_REAL_SENSOR_DATA"):
            raise ValueError
    try:
        urllib.request.urlopen(base + "/v1/snapshot", timeout=3)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise ValueError from None
    else:
        raise ValueError
except Exception:
    raise SystemExit("BLOCKED: synthetic-only HTTP guard failed") from None
print("PASS: Core receives synthetic-only diagnostic; snapshot disabled")
' </dev/null; then
  :
else
  echo "BLOCKED: diagnostic-only App not verified; no mount attestation"
  exit 1
fi

MOUNT=$(docker inspect --type container "$APP" --format \
  '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Source}}{{end}}{{end}}')
[ "$MOUNT" = "$EXPECTED" ] || {
  echo "BLOCKED: container /data host mount mismatch"
  exit 1
}
echo "PASS: App container /data bind matches dedicated Supervisor data directory"
[ -d "$EXPECTED" ] && [ ! -L "$EXPECTED" ] || {
  echo "BLOCKED: host App data directory absent or symlinked"
  exit 1
}
HOST_META=$(stat -c '%a:%u:%g' "$EXPECTED") || {
  echo "BLOCKED: cannot stat App host data directory"
  exit 1
}
CONTAINER_META=$(docker exec "$APP" stat -c '%a:%u:%g' /data </dev/null) || {
  echo "BLOCKED: cannot stat in-container /data"
  exit 1
}
UID=$(docker exec "$APP" id -u </dev/null) || {
  echo "BLOCKED: cannot inspect App effective UID"
  exit 1
}
echo "INFO: host App data mode:uid:gid=$HOST_META"
echo "INFO: container /data mode:uid:gid=$CONTAINER_META"
echo "INFO: App process probe UID=$UID"
[ "$HOST_META" = "$CONTAINER_META" ] || {
  echo "BLOCKED: host/container data identity differs"
  exit 1
}
case "$CONTAINER_META" in
  755:0:0|0755:0:0) : ;;
  *) echo "REVIEW: unexpected App data mode or owner"; exit 1 ;;
esac
[ "$UID" = 0 ] || {
  echo "BLOCKED: App Python UID differs from verified data owner"
  exit 1
}
echo "PASS: App /data owner/mode matches importer policy (no credential read)"
echo "===== MOUNT / UID ATTESTATION COMPLETE (NO CHANGES) ====="
