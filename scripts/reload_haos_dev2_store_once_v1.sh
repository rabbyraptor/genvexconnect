#!/bin/sh
# Explicitly authorized one-time local App store CATALOG reload.
# No install, update, backup, App start, source write, profile or RPC.
set -eu
umask 077

case "${1:---preflight}" in
  --preflight)
    [ "$#" -eq 1 ] || exit 2
    echo "===== DEV2 SUPERVISOR STORE RELOAD PREFLIGHT ====="
    echo "Preflight is inert; approved execution reloads the App catalog ONCE."
    echo "Never installs, updates, starts Apps or reads App-private data."
    echo "PASS: inert preflight"
    exit 0 ;;
  --execute-approved) [ "$#" -eq 1 ] || exit 2 ;;
  *) echo "Usage: sh reload_haos_dev2_store_once_v1.sh --preflight|--execute-approved" >&2; exit 2 ;;
esac

echo "===== DEV2 SUPERVISOR ONE-TIME STORE RELOAD ====="
for cmd in ha docker sha256sum; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "BLOCKED: required tool missing"; exit 1;
  }
done

# Never store, log, or print private Supervisor App options.
check_stopped() {
  META=$(ha apps info local_genvex_nabto_remote </dev/null 2>/dev/null |
    sed -n '/^state: /p; /^boot: /p; /^version: /p') || {
    echo "BLOCKED: Supervisor App info unavailable"; return 1;
  }
  STATE=$(printf '%s\n' "$META" | sed -n 's/^state: *//p')
  BOOT=$(printf '%s\n' "$META" | sed -n 's/^boot: *//p')
  VERSION=$(printf '%s\n' "$META" | sed -n 's/^version: *//p')
  [ "$STATE" = stopped ] && [ "$BOOT" = manual ] &&
    [ "$VERSION" = 0.1.0-dev1 ] || {
    echo "BLOCKED: installed App not stopped/manual/dev1"; return 1;
  }
  if docker inspect --type container app_local_genvex_nabto_remote >/dev/null 2>&1; then
    RUNNING=$(docker inspect --type container app_local_genvex_nabto_remote --format '{{.State.Running}}' 2>/dev/null) || {
      echo "BLOCKED: Docker App inspect failed"; return 1;
    }
    [ "$RUNNING" = false ] || {
      echo "BLOCKED: experimental App container running"; return 1;
    }
  fi
}
check_stopped
echo "PASS: installed App stopped/manual/dev1 with no running dedicated container"

BASE=/mnt/data/supervisor/apps/local
SRC="$BASE/genvex_nabto_remote"
BACKUP="$BASE/.genvex-remote-dev1-source-backup"
STAGE="$BASE/.genvex-remote-dev2-source-stage"
[ -d "$SRC" ] && [ ! -L "$SRC" ] &&
  [ -d "$BACKUP" ] && [ ! -L "$BACKUP" ] &&
  [ ! -e "$STAGE" ] && [ ! -L "$STAGE" ] || {
  echo "BLOCKED: dev2 source, retained dev1 backup or temporary stage invalid"; exit 1;
}
for line in \
  "$SRC/config.yaml:9c3099526543b19d6227cc8e56fbdc63b02c1c1635deff5a08f7afb7f0b1abb4" \
  "$SRC/runtime/profile_provision.py:f5b4580faeacedd1d2f73f1392864198b457af230d723217f49afa68949b67a6" \
  "$BACKUP/config.yaml:5c15ac644063f1a0fbcbcc3fd2050a56715922bf7f7f5640032b6f49bcdbfaac" \
  "$BACKUP/runtime/profile_provision.py:3d35505bfc12b24cc0f68e0a437c6fce047ffe2613ab13ccb10fe2959ec1fe82"; do
  FILE=${line%:*}
  EXPECTED=${line##*:}
  [ -f "$FILE" ] && [ ! -L "$FILE" ] || {
    echo "BLOCKED: source file absent or symlinked"; exit 1;
  }
  DIGEST=$(sha256sum "$FILE" </dev/null) || {
    echo "BLOCKED: source checksum unavailable"; exit 1;
  }
  [ "${DIGEST%% *}" = "$EXPECTED" ] || {
    echo "BLOCKED: source does not match pinned dev1/dev2 candidate"; exit 1;
  }
done
echo "PASS: pinned dev2 source and original dev1 source backup unchanged"

# Once the app has already been recognized as dev2, do not reload twice.
CATALOG=$(ha apps info local_genvex_nabto_remote </dev/null 2>/dev/null |
  sed -n '/^version_latest: /p; /^update_available: /p') || {
  echo "BLOCKED: cannot read current store metadata"; exit 1;
}
LATEST=$(printf '%s\n' "$CATALOG" | sed -n 's/^version_latest: *//p')
UPDATE=$(printf '%s\n' "$CATALOG" | sed -n 's/^update_available: *//p')
case "$LATEST:$UPDATE" in
  0.1.0-dev1:false|0.1.0-dev1:|:false|:) : ;;
  0.1.0-dev2:true)
    echo "PASS: dev2 is already offered; store reload not needed"
    echo "===== DEV2 STORE STATUS VERIFIED WITHOUT RELOAD ====="
    exit 0 ;;
  *) echo "BLOCKED: unexpected pre-reload catalog version or update flag"; exit 1 ;;
esac

echo "ACTION: one approved Supervisor App store catalog reload"
# Suppress CLI output; it may contain unrelated repository details.
if ha store reload </dev/null >/dev/null 2>/dev/null; then
  echo "PASS: Supervisor store reload command returned success"
else
  echo "BLOCKED: store reload failed; no retry or further mutation"
  exit 1
fi

# A store reload may finish asynchronously. Record status without loops,
# retries or automatic App installation.
check_stopped || {
  echo "BLOCKED: App lifecycle changed unexpectedly after catalog reload"
  exit 1
}
echo "PASS: installed App remains stopped/manual/dev1 after reload"
CATALOG=$(ha apps info local_genvex_nabto_remote </dev/null 2>/dev/null |
  sed -n '/^version_latest: /p; /^update_available: /p') || {
  echo "BLOCKED: cannot read post-reload catalog version"; exit 1;
}
LATEST=$(printf '%s\n' "$CATALOG" | sed -n 's/^version_latest: *//p')
UPDATE=$(printf '%s\n' "$CATALOG" | sed -n 's/^update_available: *//p')
echo "INFO: catalog version_latest=${LATEST:-unknown}"
echo "INFO: catalog update_available=${UPDATE:-unknown}"
if [ "$LATEST" = 0.1.0-dev2 ] && [ "$UPDATE" = true ]; then
  echo "PASS: Supervisor offers dev2 update, not installed"
else
  echo "REVIEW: dev2 not yet confirmed by Supervisor; do not force update"
fi
echo "PASS: no App build/update/start and no App-private data access"
echo "===== DEV2 SUPERVISOR STORE RELOAD CHECK COMPLETE ====="
