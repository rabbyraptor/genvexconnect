#!/bin/sh
# HAOS read-only metadata-only App-private storage audit. No credential reads.
set -eu
umask 077

case "${1:---preflight}" in
  --preflight)
    [ "$#" -eq 1 ] || exit 2
    echo "===== REMOTE PRIVATE STORAGE PREFLIGHT ====="
    echo "Read-only metadata: Supervisor mount, dedicated App directory, safety."
    echo "No file contents, directory listing, credentials, installs or RPC."
    echo "PASS: inert preflight"
    exit 0 ;;
  --execute-readonly) [ "$#" -eq 1 ] || exit 2 ;;
  *) echo "Usage: sh audit_haos_remote_private_storage_v1.sh --preflight|--execute-readonly" >&2; exit 2 ;;
esac

echo "===== REMOTE PRIVATE STORAGE (READ ONLY) ====="
if ! command -v ha >/dev/null 2>&1 ||
   ! command -v docker >/dev/null 2>&1; then
  echo "BLOCKED: Supervisor CLI or Docker unavailable"
  exit 1
fi

# Never retain raw Supervisor options in memory or print them.
META=$(ha apps info local_genvex_nabto_remote </dev/null 2>/dev/null |
  sed -n '/^state: /p; /^boot: /p; /^version: /p') || {
  echo "BLOCKED: App metadata unavailable"
  exit 1
}
STATE=$(printf '%s\n' "$META" | sed -n 's/^state: *//p')
BOOT=$(printf '%s\n' "$META" | sed -n 's/^boot: *//p')
VERSION=$(printf '%s\n' "$META" | sed -n 's/^version: *//p')
if [ "$STATE" != stopped ] || [ "$BOOT" != manual ] ||
   [ "$VERSION" != 0.1.0-dev1 ]; then
  echo "BLOCKED: expected stopped/manual/0.1.0-dev1 not verified"
  exit 1
fi
echo "PASS: dedicated Supervisor App is stopped and manual"

if docker inspect --type container app_local_genvex_nabto_remote >/dev/null 2>&1; then
  RUNNING=$(docker inspect --type container app_local_genvex_nabto_remote --format '{{.State.Running}}')
  [ "$RUNNING" = false ] || {
    echo "BLOCKED: remote App Docker container still running"
    exit 1
  }
fi
echo "PASS: no running dedicated remote App container"

# The /data bind is independently validated. Never assume that host paths
# follow Supervisor container paths if this mount cannot be established.
SUPERVISOR_DATA=$(docker inspect --type container hassio_supervisor   --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Source}}{{end}}{{end}}' 2>/dev/null) || {
  echo "BLOCKED: Supervisor data mount unavailable"
  exit 1
}
if [ "$SUPERVISOR_DATA" != /mnt/data/supervisor ]; then
  echo "BLOCKED: Supervisor data mount differs from known HAOS mapping"
  exit 1
fi
echo "PASS: Supervisor /data maps to expected HAOS storage root"

APP_DIR=/mnt/data/supervisor/apps/data/local_genvex_nabto_remote
if [ -L "$APP_DIR" ]; then
  echo "BLOCKED: dedicated App storage is a symlink"
  exit 1
fi
if [ ! -d "$APP_DIR" ]; then
  echo "NOT READY: dedicated App storage directory absent"
  exit 1
fi
# Metadata only, never enumerate private App files or read options.json.
MODE=$(stat -c '%a' "$APP_DIR" 2>/dev/null) || {
  echo "BLOCKED: cannot stat dedicated App storage"
  exit 1
}
case "$MODE" in
  700|0700) echo "PASS: dedicated App storage permissions are 0700" ;;
  *) echo "BLOCKED: App storage permissions are not 0700"; exit 1 ;;
esac
echo "PASS: storage directory present, no contents read or enumerated"
echo "===== REMOTE PRIVATE STORAGE AUDIT COMPLETE ====="
