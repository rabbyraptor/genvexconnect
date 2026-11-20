#!/bin/sh
# Read-only gate for *existing* dev1 local App source before a dev2 swap.
# Refuses unexpected source contents. Never touches App-private /data.
set -eu
umask 077
case "${1:---preflight}" in
  --preflight)
    [ "$#" -eq 1 ] || exit 2
    echo "===== GENVEX DEV2 SOURCE TRANSACTION PREFLIGHT ====="
    echo "Read-only: verifies stopped dev1 App and exact source-tree baseline."
    echo "No file modifications, credentials, Supervisor reload or Nabto RPC."
    echo "PASS: inert preflight"
    exit 0 ;;
  --execute-readonly) [ "$#" -eq 1 ] || exit 2 ;;
  *) echo "Usage: sh audit_haos_dev2_source_transaction_preflight_v1.sh --preflight|--execute-readonly" >&2; exit 2 ;;
esac

echo "===== GENVEX DEV2 SOURCE TRANSACTION GATE (READ ONLY) ====="
for cmd in ha docker find stat sha256sum; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "BLOCKED: required tool missing"; exit 1; }
done
# Capture only allowlisted top-level metadata, not Supervisor options.
META=$(ha apps info local_genvex_nabto_remote </dev/null 2>/dev/null |
  sed -n '/^state: /p; /^boot: /p; /^version: /p') || {
  echo "BLOCKED: Supervisor metadata unavailable"; exit 1;
}
STATE=$(printf '%s\n' "$META" | sed -n 's/^state: *//p')
BOOT=$(printf '%s\n' "$META" | sed -n 's/^boot: *//p')
VERSION=$(printf '%s\n' "$META" | sed -n 's/^version: *//p')
[ "$STATE" = stopped ] && [ "$BOOT" = manual ] && [ "$VERSION" = 0.1.0-dev1 ] || {
  echo "BLOCKED: installed App must be stopped/manual/dev1"; exit 1;
}
if docker inspect --type container app_local_genvex_nabto_remote >/dev/null 2>&1; then
  RUNNING=$(docker inspect --type container app_local_genvex_nabto_remote --format '{{.State.Running}}')
  [ "$RUNNING" = false ] || { echo "BLOCKED: remote App container running"; exit 1; }
fi
echo "PASS: installed dev1 stopped/manual, no running dedicated container"

BASE=/mnt/data/supervisor/apps/local
SRC="$BASE/genvex_nabto_remote"
[ -d "$SRC" ] && [ ! -L "$SRC" ] && [ -d "$SRC/runtime" ] &&
  [ ! -L "$SRC/runtime" ] || {
  echo "BLOCKED: source directory missing or linked"; exit 1;
}
# Walk ONLY the local source tree, never Supervisor's apps/data.
# Deny any unexpected file/dir/symlink before archiving or future replacement.
BAD=$(find "$SRC" -mindepth 1 -print | while IFS= read -r path; do
  rel=${path#"$SRC"/}
  case "$rel" in
    runtime) [ -d "$path" ] && [ ! -L "$path" ] || echo unsafe ;;
    Dockerfile|config.yaml|run.sh|runtime/*.py)
      [ -f "$path" ] && [ ! -L "$path" ] || echo unsafe ;;
    *) echo unexpected ;;
  esac
done | head -n 1) || {
  echo "BLOCKED: cannot validate source tree"; exit 1;
}
[ -z "$BAD" ] || { echo "BLOCKED: unexpected or linked source entries"; exit 1; }
echo "PASS: existing local App source tree contains only allowlisted paths"

# Confirm the exact five operator-verified baseline files. No secrets are
# accessed; only these source file hashes are calculated.
while read -r REL SHA; do
  [ -n "$REL" ] || continue
  FILE="$SRC/$REL"
  [ -f "$FILE" ] && [ ! -L "$FILE" ] || {
    echo "BLOCKED: baseline source file unavailable"; exit 1;
  }
  HASH=$(sha256sum "$FILE" </dev/null)
  HASH=${HASH%% *}
  [ "$HASH" = "$SHA" ] || {
    echo "BLOCKED: installed App source differs from recorded baseline"; exit 1;
  }
done <<'BASELINE'
config.yaml 5c15ac644063f1a0fbcbcc3fd2050a56715922bf7f7f5640032b6f49bcdbfaac
Dockerfile 5c7edfb109ccad4b09a19ff28c3173e405bcb33eb26034174ee10de83d2f4cdd
run.sh 50c68a9defb3c47621ab6d3b901b3e645ac19f539616457f469a1cb76a91f398
runtime/app_bootstrap.py 9e8862450d6204d21136baae25ce37aa24aa591f1008842c5914911517db7db1
runtime/profile_provision.py 3d35505bfc12b24cc0f68e0a437c6fce047ffe2613ab13ccb10fe2959ec1fe82
BASELINE
echo "PASS: five installed dev1 baseline SHA256 values match"

# No preexisting transaction staging or backup may be silently overwritten.
for name in .genvex-remote-dev2-source-stage .genvex-remote-dev1-source-backup; do
  if [ -e "$BASE/$name" ] || [ -L "$BASE/$name" ]; then
    echo "BLOCKED: source transaction already staged or backed up"; exit 1;
  fi
done
echo "PASS: source transaction staging/backup names unoccupied"
echo "PASS: no source or App-private data modified"
echo "===== GENVEX DEV2 SOURCE TRANSACTION GATE COMPLETE ====="
