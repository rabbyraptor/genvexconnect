#!/usr/bin/env bash
# Explicit, operator-run DEV2 -> DEV3 App update. Never start the App.
# Only local App source is swapped; Supervisor separately backs up the App.
set -euo pipefail
umask 077

if [ "${1:-}" != "--apply" ] || [ "$#" -ne 1 ]; then
  echo "Usage: bash scripts/upgrade_genvex_remote_dev3_from_deck.sh --apply" >&2
  exit 2
fi

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
[ "$(git branch --show-current)" = "feature/dev3-live-once" ] || {
  echo "BLOCKED: require feature/dev3-live-once checkout"
  exit 1
}
[ -z "$(git status --porcelain --untracked-files=no)" ] || {
  echo "BLOCKED: tracked local changes"
  exit 1
}

SSH=(ssh -T -p 22222 -o BatchMode=yes root@rabbyshome.duckdns.org)

echo "===== DEV3 SOURCE PACKAGE ====="
python3 scripts/package_remote_diagnostic_app.py
cp -- scripts/audit_haos_dev3_source_transaction_preflight_v1.sh dist/
ARCHIVE=dist/genvex-nabto-remote-local-app-source.tar.gz
SUMS=dist/APP_SOURCE_SHA256SUMS

echo "===== DEV2 RUNNING-STATE GATE / STOP ====="
"${SSH[@]}" 'sh -s' <<'REMOTE'
set -eu
# Only parse public top-level metadata. App info also contains passwords.
META=$(ha apps info local_genvex_nabto_remote </dev/null 2>/dev/null |
  sed -n '/^state: /p; /^boot: /p; /^version: /p')
get() { printf '%s\n' "$META" | sed -n "s/^$1: *//p"; }
[ "$(get version)" = "0.1.0-dev2" ] &&
  [ "$(get boot)" = "manual" ] || {
  echo "BLOCKED: expected manually managed dev2 App"; exit 1;
}
case "$(get state)" in
  started)
    echo "ACTION: stopping read-only dev2 polling"
    ha apps stop local_genvex_nabto_remote </dev/null >/dev/null 2>/dev/null || {
      echo "BLOCKED: App stop failed"; exit 1;
    }
    ;;
  stopped) echo "PASS: App already stopped" ;;
  *) echo "BLOCKED: unexpected App state"; exit 1 ;;
esac
META=$(ha apps info local_genvex_nabto_remote </dev/null 2>/dev/null |
  sed -n '/^state: /p; /^boot: /p; /^version: /p')
printf '%s\n' "$META" | grep -qx 'state: stopped' || {
  echo "BLOCKED: App not stopped"; exit 1;
}
echo "PASS: dev2 stopped for code update"
REMOTE

echo "===== DEV3 SOURCE READ-ONLY PREFLIGHT ====="
bash scripts/upgrade_remote_local_app_source_dev3.sh --preflight "$ARCHIVE" "$SUMS"

echo "===== DEV3 SOURCE BACKUP / ATOMIC SWAP ====="
bash scripts/upgrade_remote_local_app_source_dev3.sh --apply "$ARCHIVE" "$SUMS"

echo "===== DEV3 SUPERVISOR BACKUP / UPDATE ====="
"${SSH[@]}" 'sh -s -- --execute-approved' < scripts/update_haos_genvex_remote_dev3_with_backup_v1.sh

echo "PASS: dev3 installed and stopped; no automatic Nabto polling started"
echo "PASS: dev2 source backup retained; Supervisor backup requested"
echo "NEXT: inspect status before manually starting dev3"
