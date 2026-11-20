#!/bin/sh
# Read-only HAOS Supervisor update readiness gate. Does NOT reload the store,
# create a backup, rebuild/update the App, open /data or start anything.
set -eu
umask 077
case "${1:---preflight}" in
  --preflight)
    [ "$#" -eq 1 ] || exit 2
    echo "===== DEV2 SUPERVISOR UPDATE READINESS PREFLIGHT ====="
    echo "Read-only: stopped App, source + backup, update metadata and free disk."
    echo "No App-private data, store reload, backup creation, install or RPC."
    echo "PASS: inert preflight"
    exit 0 ;;
  --execute-readonly) [ "$#" -eq 1 ] || exit 2 ;;
  *) echo "Usage: sh audit_haos_dev2_supervisor_update_readiness_v1.sh --preflight|--execute-readonly" >&2; exit 2 ;;
esac

echo "===== DEV2 SUPERVISOR UPDATE READINESS (READ ONLY) ====="
for cmd in ha docker sha256sum df; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "BLOCKED: required tool missing"
    exit 1
  }
done
# Supervisor info includes private options: ONLY parse top-level metadata.
INFO=$(ha apps info local_genvex_nabto_remote </dev/null 2>/dev/null |
  sed -n '/^state: /p; /^boot: /p; /^version: /p; /^version_latest: /p; /^update_available: /p') || {
  echo "BLOCKED: Supervisor App info failed"
  exit 1
}
VALUE() { printf '%s\n' "$INFO" | sed -n "s/^$1: *//p"; }
STATE=$(VALUE state)
BOOT=$(VALUE boot)
VERSION=$(VALUE version)
LATEST=$(VALUE version_latest)
UPDATE=$(VALUE update_available)
[ "$STATE" = stopped ] && [ "$BOOT" = manual ] &&
  [ "$VERSION" = 0.1.0-dev1 ] || {
  echo "BLOCKED: installed App must be stopped/manual/dev1"
  exit 1
}
if docker inspect --type container app_local_genvex_nabto_remote >/dev/null 2>&1; then
  RUNNING=$(docker inspect --type container app_local_genvex_nabto_remote --format '{{.State.Running}}') || {
    echo "BLOCKED: Docker inspect failed"
    exit 1
  }
  [ "$RUNNING" = false ] || { echo "BLOCKED: dedicated App running"; exit 1; }
fi
echo "PASS: installed App stopped/manual/dev1; no running remote container"

# Before a store reload, version_latest may still report dev1. Report
# metadata honestly rather than claiming dev2 is offered.
case "$LATEST" in
  ''|0.1.0-dev1|0.1.0-dev2) : ;;
  *) echo "REVIEW: unexpected catalog version; do not update"; exit 1 ;;
esac
case "$UPDATE" in
  ''|true|false) : ;;
  *) echo "REVIEW: unexpected update flag; do not update"; exit 1 ;;
esac
echo "INFO: Supervisor catalog version_latest=${LATEST:-unknown}"
echo "INFO: Supervisor update_available=${UPDATE:-unknown}"
if [ "$LATEST" = 0.1.0-dev2 ] && [ "$UPDATE" = true ]; then
  echo "PASS: Supervisor already offers dev2"
else
  echo "NOT READY: Supervisor has not yet confirmed an available dev2 update"
  echo "REVIEW: store reload may be needed; this audit NEVER performs it"
fi

BASE=/mnt/data/supervisor/apps/local
SRC="$BASE/genvex_nabto_remote"
BACKUP="$BASE/.genvex-remote-dev1-source-backup"
STAGE="$BASE/.genvex-remote-dev2-source-stage"
[ -d "$SRC" ] && [ ! -L "$SRC" ] &&
  [ -d "$BACKUP" ] && [ ! -L "$BACKUP" ] &&
  [ ! -e "$STAGE" ] && [ ! -L "$STAGE" ] || {
  echo "BLOCKED: dev2 source, old backup or staging state invalid"
  exit 1
}
for line in \
  "$SRC/config.yaml:9c3099526543b19d6227cc8e56fbdc63b02c1c1635deff5a08f7afb7f0b1abb4" \
  "$SRC/runtime/profile_provision.py:f5b4580faeacedd1d2f73f1392864198b457af230d723217f49afa68949b67a6" \
  "$BACKUP/config.yaml:5c15ac644063f1a0fbcbcc3fd2050a56715922bf7f7f5640032b6f49bcdbfaac" \
  "$BACKUP/runtime/profile_provision.py:3d35505bfc12b24cc0f68e0a437c6fce047ffe2613ab13ccb10fe2959ec1fe82"; do
  FILE=${line%:*}
  EXPECTED=${line##*:}
  [ -f "$FILE" ] && [ ! -L "$FILE" ] || {
    echo "BLOCKED: source file missing or linked"
    exit 1
  }
  DIGEST=$(sha256sum "$FILE" </dev/null) || {
    echo "BLOCKED: SHA256 source verification failed"
    exit 1
  }
  [ "${DIGEST%% *}" = "$EXPECTED" ] || {
    echo "BLOCKED: source differs from pinned candidate or backup"
    exit 1
  }
done
echo "PASS: dev2 and dev1 backup critical source SHA256 unchanged"

# Check availability, not a speculative minimum size. Never traverse data.
FREE=$(df -Pk "$BASE" 2>/dev/null | awk 'NR==2 {print $4}') || {
  echo "BLOCKED: free space unavailable"
  exit 1
}
case "$FREE" in
  ''|*[!0-9]*) echo "BLOCKED: invalid free space metadata"; exit 1 ;;
esac
echo "INFO: free KiB on local source filesystem=$FREE"
[ "$FREE" -ge 524288 ] || {
  echo "REVIEW: less than 512 MiB free; cannot authorize update"
  exit 1
}
echo "PASS: at least 512 MiB disk headroom on local source filesystem"
echo "PASS: read-only only; no source changes or private data read"
echo "===== DEV2 SUPERVISOR UPDATE READINESS AUDIT COMPLETE ====="
