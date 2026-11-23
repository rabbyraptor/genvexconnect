#!/bin/sh
# Read-only post-swap attestation of exact dev2 source and retained dev1 backup.
# No App-private /data access, Supervisor store reload, App update/start or RPC.
set -eu
umask 077

case "${1:---preflight}" in
  --preflight)
    [ "$#" -eq 1 ] || exit 2
    echo "===== DEV2 SOURCE SWAP RESULT PREFLIGHT ====="
    echo "Read-only: exact source and backup SHA256, stopped App, no private data."
    echo "PASS: inert preflight"
    exit 0 ;;
  --execute-readonly) [ "$#" -eq 1 ] || exit 2 ;;
  *) echo "Usage: sh audit_haos_dev2_source_swap_result_v1.sh --preflight|--execute-readonly" >&2; exit 2 ;;
esac

echo "===== DEV2 SOURCE SWAP RESULT (READ ONLY) ====="
for cmd in ha docker sha256sum find; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "BLOCKED: required tool missing"; exit 1; }
done

# Never print or store the full Supervisor options block.
META=$(ha apps info local_genvex_nabto_remote </dev/null 2>/dev/null |
  sed -n '/^state: /p; /^boot: /p; /^version: /p') || {
  echo "BLOCKED: Supervisor metadata unavailable"; exit 1;
}
STATE=$(printf '%s\n' "$META" | sed -n 's/^state: *//p')
BOOT=$(printf '%s\n' "$META" | sed -n 's/^boot: *//p')
VERSION=$(printf '%s\n' "$META" | sed -n 's/^version: *//p')
[ "$STATE" = stopped ] && [ "$BOOT" = manual ] && [ "$VERSION" = 0.1.0-dev1 ] || {
  echo "BLOCKED: installed Supervisor App not stopped/manual/dev1"; exit 1;
}
if docker inspect --type container app_local_genvex_nabto_remote >/dev/null 2>&1; then
  RUNNING=$(docker inspect --type container app_local_genvex_nabto_remote --format '{{.State.Running}}' 2>/dev/null) || {
    echo "BLOCKED: cannot inspect dedicated App container"; exit 1;
  }
  [ "$RUNNING" = false ] || { echo "BLOCKED: dedicated App is running"; exit 1; }
fi
echo "PASS: installed Supervisor App remains stopped/manual/dev1"

BASE=/mnt/data/supervisor/apps/local
SRC="$BASE/genvex_nabto_remote"
BACKUP="$BASE/.genvex-remote-dev1-source-backup"
STAGE="$BASE/.genvex-remote-dev2-source-stage"
[ ! -e "$STAGE" ] && [ ! -L "$STAGE" ] || {
  echo "BLOCKED: temporary source stage still exists"; exit 1;
}
echo "PASS: temporary stage absent"

# Only SOURCE and its retained source backup. Never inspect apps/data.
for ROOT in "$SRC" "$BACKUP"; do
  [ -d "$ROOT" ] && [ ! -L "$ROOT" ] &&
    [ -d "$ROOT/runtime" ] && [ ! -L "$ROOT/runtime" ] || {
    echo "BLOCKED: source or backup missing or linked"; exit 1;
  }
  if ! find "$ROOT" -mindepth 1 -print >/dev/null 2>&1; then
    echo "BLOCKED: unable to enumerate source-only tree"; exit 1;
  fi
  BAD=$(find "$ROOT" -mindepth 1 -print | while IFS= read -r file; do
    rel=${file#"$ROOT"/}
    case "$rel" in
      runtime) [ -d "$file" ] && [ ! -L "$file" ] || echo unsafe ;;
      config.yaml|Dockerfile|run.sh|runtime/*.py)
        [ -f "$file" ] && [ ! -L "$file" ] || echo unsafe ;;
      *) echo unexpected ;;
    esac
  done) || {
    echo "BLOCKED: source tree allowlist traversal failed"; exit 1;
  }
  [ -z "$BAD" ] || {
    echo "BLOCKED: unexpected or linked source tree entries"; exit 1;
  }
done
echo "PASS: dev2 source and dev1 backup both exist, with allowlisted source entries"

while read -r REL DEV1 DEV2; do
  [ -n "$REL" ] || continue
  for TREE in dev1 dev2; do
    case "$TREE" in
      dev1) ROOT=$BACKUP; EXPECTED=$DEV1 ;;
      dev2) ROOT=$SRC; EXPECTED=$DEV2 ;;
    esac
    FILE="$ROOT/$REL"
    [ -f "$FILE" ] && [ ! -L "$FILE" ] || {
      echo "BLOCKED: required source file missing or linked"; exit 1;
    }
    DIGEST=$(sha256sum "$FILE" </dev/null) || {
      echo "BLOCKED: cannot hash source file"; exit 1;
    }
    DIGEST=${DIGEST%% *}
    [ "$DIGEST" = "$EXPECTED" ] || {
      echo "BLOCKED: $TREE source fingerprint mismatch: $REL"; exit 1;
    }
  done
done <<'FINGERPRINTS'
config.yaml 5c15ac644063f1a0fbcbcc3fd2050a56715922bf7f7f5640032b6f49bcdbfaac 9c3099526543b19d6227cc8e56fbdc63b02c1c1635deff5a08f7afb7f0b1abb4
Dockerfile 5c7edfb109ccad4b09a19ff28c3173e405bcb33eb26034174ee10de83d2f4cdd 5c7edfb109ccad4b09a19ff28c3173e405bcb33eb26034174ee10de83d2f4cdd
run.sh 50c68a9defb3c47621ab6d3b901b3e645ac19f539616457f469a1cb76a91f398 50c68a9defb3c47621ab6d3b901b3e645ac19f539616457f469a1cb76a91f398
runtime/app_bootstrap.py 9e8862450d6204d21136baae25ce37aa24aa591f1008842c5914911517db7db1 9e8862450d6204d21136baae25ce37aa24aa591f1008842c5914911517db7db1
runtime/profile_provision.py 3d35505bfc12b24cc0f68e0a437c6fce047ffe2613ab13ccb10fe2959ec1fe82 f5b4580faeacedd1d2f73f1392864198b457af230d723217f49afa68949b67a6
FINGERPRINTS
echo "PASS: dev1 backup matches five previously verified original source hashes"
echo "PASS: dev2 source matches five pinned candidate source hashes"
echo "PASS: no App data access or Supervisor change performed"
echo "===== DEV2 SOURCE SWAP RESULT VERIFIED ====="
