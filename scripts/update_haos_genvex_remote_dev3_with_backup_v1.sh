#!/bin/sh
# PREPARED ONLY: Supervisor update requires separate explicit operator approval.
# No credentials, /data inspection, App start/stop, store reload or RPC.
set -eu
umask 077
case "$1" in
  --preflight)
    [ "$#" -eq 1 ] || exit 2
    echo "===== DEV3 BACKUP UPDATE PREFLIGHT ====="
    echo "Inert preflight. Separately approved execution uses ha apps update --backup."
    echo "PASS: inert preflight"
    exit 0 ;;
  --execute-approved) [ "$#" -eq 1 ] || exit 2 ;;
  *) echo "Usage: sh update_haos_genvex_remote_dev3_with_backup_v1.sh --preflight|--execute-approved" >&2; exit 2 ;;
esac

echo "===== DEV3 SUPERVISOR BACKUP-ENABLED UPDATE ====="
for exe in ha docker sha256sum df; do
  command -v "$exe" >/dev/null 2>&1 || {
    echo "BLOCKED: required command missing"; exit 1;
  }
done
# Restrict Supervisor data to top-level allowlisted metadata.
safe_info() {
  ha apps info local_genvex_nabto_remote </dev/null 2>/dev/null |
    sed -n '/^state: /p; /^boot: /p; /^version: /p; /^version_latest: /p; /^update_available: /p'
}
# Check stopped/manual dev2 BEFORE touching even the Supervisor catalog.
META=$(safe_info) || { echo "BLOCKED: App info unavailable"; exit 1; }
readfield() { printf '%s\n' "$META" | sed -n "s/^$1: *//p"; }
[ "$(readfield state)" = stopped ] &&
[ "$(readfield boot)" = manual ] &&
[ "$(readfield version)" = 0.1.0-dev2 ] || {
  echo "BLOCKED: installed App must be stopped/manual/dev2"; exit 1;
}
if docker inspect --type container app_local_genvex_nabto_remote >/dev/null 2>&1; then
  RUNNING=$(docker inspect --type container app_local_genvex_nabto_remote --format '{{.State.Running}}') || exit 1
  [ "$RUNNING" = false ] || {
    echo "BLOCKED: dedicated App container is running"; exit 1;
  }
fi
echo "PASS: installed App stopped/manual/dev2; dev3 available"

BASE=/mnt/data/supervisor/apps/local
SRC="$BASE/genvex_nabto_remote"
OLD="$BASE/.genvex-remote-dev2-source-backup"
STAGE="$BASE/.genvex-remote-dev3-source-stage"
[ -d "$SRC" ] && [ ! -L "$SRC" ] &&
[ -d "$OLD" ] && [ ! -L "$OLD" ] &&
[ ! -e "$STAGE" ] && [ ! -L "$STAGE" ] || {
  echo "BLOCKED: dev3 source, backup or stage state invalid"; exit 1;
}
# New source was content-hash verified and staged by the separate
# source-only transaction; verify version and retained dev2 baseline here.
[ -f "$SRC/config.yaml" ] && [ ! -L "$SRC/config.yaml" ] &&
  grep -qx 'version: "0.1.0-dev3"' "$SRC/config.yaml" &&
  [ -f "$SRC/runtime/sdk_snapshot_adapter.py" ] &&
  [ ! -L "$SRC/runtime/sdk_snapshot_adapter.py" ] || {
  echo "BLOCKED: dev3 source not staged"; exit 1;
}
for line in \
  "$OLD/config.yaml:9c3099526543b19d6227cc8e56fbdc63b02c1c1635deff5a08f7afb7f0b1abb4" \
  "$OLD/runtime/profile_provision.py:f5b4580faeacedd1d2f73f1392864198b457af230d723217f49afa68949b67a6"; do
  FILE=${line%:*}
  EXPECTED=${line##*:}
  [ -f "$FILE" ] && [ ! -L "$FILE" ] || {
    echo "BLOCKED: dev2 source backup missing"; exit 1;
  }
  DIGEST=$(sha256sum "$FILE" </dev/null) || exit 1
  [ "${DIGEST%% *}" = "$EXPECTED" ] || {
    echo "BLOCKED: dev2 backup hash mismatch"; exit 1;
  }
done
echo "PASS: staged dev3 source and retained dev2 source backup verified"

FREE=$(df -Pk "$BASE" 2>/dev/null | awk 'NR==2 {print $4}') || exit 1
case "$FREE" in
  ''|*[!0-9]*) echo "BLOCKED: invalid disk space metadata"; exit 1 ;;
esac
[ "$FREE" -ge 524288 ] || {
  echo "BLOCKED: less than 512 MiB free"; exit 1;
}
echo "PASS: sufficient free disk headroom"

HELP=$(ha apps update --help </dev/null 2>&1) || {
  echo "BLOCKED: CLI help unavailable"; exit 1;
}
case "$HELP" in
  *--backup*) : ;;
  *) echo "BLOCKED: CLI lacks backup flag"; exit 1 ;;
esac

echo "ACTION: reloading local App catalog after source and stopped-state checks"
ha store reload </dev/null >/dev/null 2>/dev/null || {
  echo "BLOCKED: store reload failed; dev2 image unchanged"; exit 1;
}
META=$(safe_info) || { echo "BLOCKED: App info unavailable after reload"; exit 1; }
[ "$(readfield state)" = stopped ] &&
[ "$(readfield boot)" = manual ] &&
[ "$(readfield version)" = 0.1.0-dev2 ] &&
[ "$(readfield version_latest)" = 0.1.0-dev3 ] &&
[ "$(readfield update_available)" = true ] || {
  echo "BLOCKED: Supervisor did not offer dev3 as a stopped/manual dev2 update"
  exit 1
}
echo "PASS: Supervisor offers backed-up dev3 update"

# After catalog refresh, request one explicit backup-enabled App update.
# The one and only App image mutation. Supervisor makes the backup first
# and aborts on backup failure. Never retry automatically.
echo "ACTION: one backup-enabled Supervisor update requested"
if ha apps update local_genvex_nabto_remote --backup </dev/null >/dev/null 2>/dev/null; then
  echo "PASS: backup-enabled update command returned success"
else
  echo "BLOCKED: update command failed; do not retry before investigating"
  exit 1
fi

# Supervisor's source implements restart only for previously started Apps.
# Reverify anyway and do not start/stop anything if unexpected.
META=$(safe_info) || {
  echo "REVIEW: cannot inspect App after update"; exit 1;
}
STATE=$(readfield state)
VERSION=$(readfield version)
BOOT=$(readfield boot)
echo "INFO: installed version=$VERSION"
echo "INFO: installed state=$STATE"
echo "INFO: installed boot=$BOOT"
[ "$STATE" = stopped ] && [ "$BOOT" = manual ] &&
  [ "$VERSION" = 0.1.0-dev3 ] || {
  echo "REVIEW: unexpected App version or lifecycle after update"; exit 1;
}
if docker inspect --type container app_local_genvex_nabto_remote >/dev/null 2>&1; then
  RUNNING=$(docker inspect --type container app_local_genvex_nabto_remote --format '{{.State.Running}}') || exit 1
  [ "$RUNNING" = false ] || {
    echo "REVIEW: App container running unexpectedly"; exit 1;
  }
fi
echo "PASS: installed App dev3, stopped/manual, no running container"
echo "REVIEW: verify app update backup in Home Assistant backup inventory"
echo "PASS: no manual start, no profile access and no Nabto RPC"
echo "===== DEV3 SUPERVISOR UPDATE TRANSACTION COMPLETE ====="
