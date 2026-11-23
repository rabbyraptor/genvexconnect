#!/bin/sh
# Read-only readiness gate for an existing Supervisor-managed local App SOURCE.
# Does not enumerate the App data directory, access options or mutate HAOS.
set -eu
umask 077
case "${1:---preflight}" in
  --preflight)
    [ "$#" -eq 1 ] || exit 2
    echo "===== REMOTE UPDATE SOURCE PREFLIGHT ====="
    echo "Read-only: dedicated App status and allowlisted local source SHA256."
    echo "No secrets, no /data inspection, no install/update/start/reload/RPC."
    echo "PASS: inert preflight"
    exit 0 ;;
  --execute-readonly) [ "$#" -eq 1 ] || exit 2 ;;
  *) echo "Usage: sh audit_haos_remote_update_source_readonly_v1.sh --preflight|--execute-readonly" >&2; exit 2 ;;
esac

echo "===== REMOTE UPDATE SOURCE AUDIT (READ ONLY) ====="
for command in ha docker sha256sum stat; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "BLOCKED: required command unavailable"
    exit 1
  }
done
# Never capture Supervisor options: top-level allowlist only.
META=$(ha apps info local_genvex_nabto_remote </dev/null 2>/dev/null |
  sed -n '/^state: /p; /^boot: /p; /^version: /p') || {
  echo "BLOCKED: Supervisor metadata unavailable"
  exit 1
}
STATE=$(printf '%s\n' "$META" | sed -n 's/^state: *//p')
BOOT=$(printf '%s\n' "$META" | sed -n 's/^boot: *//p')
VERSION=$(printf '%s\n' "$META" | sed -n 's/^version: *//p')
[ "$STATE" = stopped ] && [ "$BOOT" = manual ] &&
  [ "$VERSION" = 0.1.0-dev1 ] || {
  echo "BLOCKED: installed App not confirmed stopped/manual/0.1.0-dev1"
  exit 1
}
echo "PASS: installed dedicated App stopped/manual/version dev1"
if docker inspect --type container app_local_genvex_nabto_remote >/dev/null 2>&1; then
  RUNNING=$(docker inspect --type container app_local_genvex_nabto_remote \
    --format '{{.State.Running}}' 2>/dev/null) || {
    echo "BLOCKED: cannot inspect App running state"
    exit 1
  }
  [ "$RUNNING" = false ] || {
    echo "BLOCKED: dedicated App container is running"
    exit 1
  }
fi
echo "PASS: dedicated App has no running container"

ROOT=/mnt/data/supervisor/apps/local/genvex_nabto_remote
[ -d "$ROOT" ] && [ ! -L "$ROOT" ] || {
  echo "BLOCKED: dedicated App source root missing or linked"
  exit 1
}
# No file enumeration. Only fixed executable/source files in the known
# local App SOURCE folder. Never touch Supervisor private data or options.
for rel in config.yaml Dockerfile run.sh runtime/app_bootstrap.py \
           runtime/profile_provision.py; do
  file="$ROOT/$rel"
  if [ ! -f "$file" ] || [ -L "$file" ]; then
    echo "BLOCKED: required source missing or linked"
    exit 1
  fi
  size=$(stat -c '%s' "$file" 2>/dev/null) || {
    echo "BLOCKED: cannot stat required source"
    exit 1
  }
  case "$size" in
    *[!0-9]*|'') echo "BLOCKED: invalid source size metadata"; exit 1 ;;
  esac
  [ "$size" -gt 0 ] && [ "$size" -le 1000000 ] || {
    echo "BLOCKED: invalid source size"
    exit 1
  }
  digest=$(sha256sum "$file" </dev/null 2>/dev/null) || {
    echo "BLOCKED: cannot calculate source digest"
    exit 1
  }
  sha=${digest%% *}
  case "$sha" in
    *[!a-f0-9]*|'') echo "BLOCKED: invalid digest"; exit 1 ;;
  esac
  [ "${#sha}" -eq 64 ] || {
    echo "BLOCKED: invalid digest length"
    exit 1
  }
  echo "SOURCE: $rel sha256=$sha"
done
echo "PASS: only allowlisted local App source files were hashed"
echo "PASS: no App-private data or configuration secrets read"
echo "===== REMOTE UPDATE SOURCE AUDIT COMPLETE ====="
