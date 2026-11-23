#!/bin/sh
# Metadata-only diagnosis after v1 rejected App directory mode != 0700.
# Never reads or lists options, PEM, tokens, or any App-private files.
set -eu
umask 077

case "${1:---preflight}" in
  --preflight)
    [ "$#" -eq 1 ] || exit 2
    echo "===== REMOTE STORAGE METADATA PREFLIGHT v2 ====="
    echo "Read-only App and parent directory modes/owners; no secrets or RPC."
    echo "PASS: inert preflight"
    exit 0 ;;
  --execute-readonly) [ "$#" -eq 1 ] || exit 2 ;;
  *) echo "Usage: sh audit_haos_remote_private_storage_v2.sh --preflight|--execute-readonly" >&2; exit 2 ;;
esac

echo "===== REMOTE STORAGE METADATA v2 (READ ONLY) ====="
if ! command -v ha >/dev/null 2>&1 ||
   ! command -v docker >/dev/null 2>&1 ||
   ! command -v stat >/dev/null 2>&1; then
  echo "BLOCKED: required metadata commands unavailable"
  exit 1
fi

# Only capture allowlisted top-level scalar lines, never full App options.
META=$(ha apps info local_genvex_nabto_remote </dev/null 2>/dev/null |
  sed -n '/^state: /p; /^boot: /p; /^version: /p') || {
  echo "BLOCKED: Supervisor status unavailable"
  exit 1
}
STATE=$(printf '%s\n' "$META" | sed -n 's/^state: *//p')
BOOT=$(printf '%s\n' "$META" | sed -n 's/^boot: *//p')
VERSION=$(printf '%s\n' "$META" | sed -n 's/^version: *//p')
if [ "$STATE" != stopped ] || [ "$BOOT" != manual ] ||
   [ "$VERSION" != 0.1.0-dev1 ]; then
  echo "BLOCKED: dedicated App must be stopped/manual/version 0.1.0-dev1"
  exit 1
fi
echo "PASS: Supervisor App stopped/manual/version verified"

if docker inspect --type container app_local_genvex_nabto_remote >/dev/null 2>&1; then
  RUNNING=$(docker inspect --type container app_local_genvex_nabto_remote --format '{{.State.Running}}')
  [ "$RUNNING" = false ] || {
    echo "BLOCKED: dedicated App container still running"
    exit 1
  }
fi
echo "PASS: dedicated App is not running"

MOUNT=$(docker inspect --type container hassio_supervisor   --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Source}}{{end}}{{end}}' 2>/dev/null) || {
  echo "BLOCKED: Supervisor data mount not readable"
  exit 1
}
[ "$MOUNT" = /mnt/data/supervisor ] || {
  echo "BLOCKED: unexpected Supervisor data mount"
  exit 1
}
echo "PASS: Supervisor mount mapping verified"

PARENT=/mnt/data/supervisor/apps/data
APP=/mnt/data/supervisor/apps/data/local_genvex_nabto_remote
for KIND in parent app; do
  case "$KIND" in
    parent) DIR=$PARENT ;;
    app) DIR=$APP ;;
  esac
  if [ -L "$DIR" ] || [ ! -d "$DIR" ]; then
    echo "BLOCKED: $KIND directory absent, symlinked, or not a directory"
    exit 1
  fi
  # No descendants inspected; only directory metadata (octal mode, numeric UID/GID).
  META_DIR=$(stat -c '%a %u %g %F' "$DIR" 2>/dev/null) || {
    echo "BLOCKED: cannot stat $KIND directory"
    exit 1
  }
  set -- $META_DIR
  [ "$4" = directory ] || {
    echo "BLOCKED: $KIND is not a directory"
    exit 1
  }
  case "$1" in
    *[!0-7]*|'') echo "BLOCKED: invalid mode metadata"; exit 1 ;;
  esac
  echo "INFO: $KIND directory mode=$1 uid=$2 gid=$3"
  if [ "$KIND" = app ]; then
    case "$1" in
      700|0700) echo "PASS: App /data directory has owner-only permissions" ;;
      *) echo "REVIEW: Supervisor-managed App /data mode differs from 0700"
         echo "NOT READY: do not chmod Supervisor storage or import credentials"
         ;;
    esac
  fi
done
echo "PASS: metadata only; no directory listing, private file access, or changes"
echo "===== REMOTE STORAGE METADATA AUDIT COMPLETE v2 ====="
