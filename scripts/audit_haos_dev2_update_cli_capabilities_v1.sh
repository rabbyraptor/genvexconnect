#!/bin/sh
# Offline-safe read-only probe: inspect only HAOS CLI update help, not App
# options or private /data. Does not update, back up, reload, or start App.
set -eu
umask 077
case "${1:---preflight}" in
  --preflight)
    [ "$#" -eq 1 ] || exit 2
    echo "===== DEV2 UPDATE CLI CAPABILITY PREFLIGHT ====="
    echo "Read-only: stopped App, dev2 offered, CLI help flags only."
    echo "Never invokes an App update, backup, reload or Nabto RPC."
    echo "PASS: inert preflight"
    exit 0 ;;
  --execute-readonly) [ "$#" -eq 1 ] || exit 2 ;;
  *) echo "Usage: sh audit_haos_dev2_update_cli_capabilities_v1.sh --preflight|--execute-readonly" >&2; exit 2 ;;
esac

echo "===== DEV2 UPDATE CLI CAPABILITY AUDIT (READ ONLY) ====="
for cmd in ha docker; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "BLOCKED: required command missing"; exit 1; }
done
META=$(ha apps info local_genvex_nabto_remote </dev/null 2>/dev/null |
  sed -n '/^state: /p; /^boot: /p; /^version: /p; /^version_latest: /p; /^update_available: /p') || {
  echo "BLOCKED: cannot read safe Supervisor metadata"; exit 1;
}
val() { printf '%s\n' "$META" | sed -n "s/^$1: *//p"; }
[ "$(val state)" = stopped ] &&
[ "$(val boot)" = manual ] &&
[ "$(val version)" = 0.1.0-dev1 ] &&
[ "$(val version_latest)" = 0.1.0-dev2 ] &&
[ "$(val update_available)" = true ] || {
  echo "BLOCKED: App must be stopped/manual/dev1 with dev2 offered"; exit 1;
}
if docker inspect --type container app_local_genvex_nabto_remote >/dev/null 2>&1; then
  RUNNING=$(docker inspect --type container app_local_genvex_nabto_remote --format '{{.State.Running}}' 2>/dev/null) || {
    echo "BLOCKED: Docker App state unavailable"; exit 1;
  }
  [ "$RUNNING" = false ] || {
    echo "BLOCKED: dedicated App is running"; exit 1;
  }
fi
echo "PASS: stopped/manual/dev1 App with dev2 update offered"

# --help is explicitly a non-mutating read. Capture and discard its content
# rather than printing the full CLI help or unknown accidental metadata.
if HELP=$(ha apps update --help </dev/null 2>&1); then
  echo "PASS: App update help query returned success"
else
  echo "REVIEW: App update help unavailable; do not guess update arguments"
  exit 1
fi
case "$HELP" in
  *--backup*) echo "INFO: CLI advertises --backup" ;;
  *) echo "INFO: CLI does not advertise --backup" ;;
esac
case "$HELP" in
  *--background*) echo "INFO: CLI advertises --background" ;;
  *) echo "INFO: CLI does not advertise --background" ;;
esac
case "$HELP" in
  *--version*) echo "INFO: CLI advertises --version" ;;
  *) echo "INFO: CLI does not advertise --version" ;;
esac

echo "PASS: no App update, App backup, store reload or start was invoked"
echo "===== DEV2 UPDATE CLI CAPABILITY AUDIT COMPLETE ====="
