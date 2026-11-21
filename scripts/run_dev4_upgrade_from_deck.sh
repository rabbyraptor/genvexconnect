#!/usr/bin/env bash
# DEV3 -> DEV4 Supervisor App upgrade with backups and disabled-by-default
# persistent sessions. Run from Steam Deck: bash <this-script> --preflight|--apply
# This operator launcher does not automatically start the App after upgrade.
set -euo pipefail
umask 077

if [[ $# -ne 1 || ( "$1" != "--apply" && "$1" != "--preflight" ) ]]; then
  echo "Usage: bash run_dev4_upgrade_from_deck.sh --preflight|--apply" >&2
  exit 2
fi
MODE="$1"
SOURCE_COMMIT="e113cf8ef036a91f50d82acfccd871d8f9223ee9"
HOST="root@rabbyshome.duckdns.org"
PORT=22222
WORK="$(mktemp -d /tmp/genvex-dev4-upgrade.XXXXXX)"
OUT="$WORK/operator-result.txt"
REMOTE_DIR=""

ssh_cmd() {
  ssh -T -p "$PORT" -o BatchMode=yes -o ServerAliveInterval=30 "$HOST" "$@"
}
cleanup() {
  if [[ -n "$REMOTE_DIR" &&
        "$REMOTE_DIR" =~ ^/mnt/data/supervisor/apps/local/\.genvex-dev4-transfer\.[A-Za-z0-9]+$ ]]; then
    ssh_cmd "rm -rf -- '$REMOTE_DIR'" </dev/null >/dev/null 2>&1 || true
  fi
  rm -rf -- "$WORK"
}
trap cleanup EXIT

run() {
  echo "===== DEV4 UPGRADE OPERATOR ====="
  echo "MODE: $MODE"
  echo "SOURCE_COMMIT: $SOURCE_COMMIT"
  curl -fsSL --max-time 120 \
    "https://codeload.github.com/rabbyraptor/genvexconnect/tar.gz/$SOURCE_COMMIT" \
    -o "$WORK/checkout.tar.gz" || return $?
  tar -xzf "$WORK/checkout.tar.gz" -C "$WORK" || return $?
  local source
  source="$(find "$WORK" -mindepth 3 -maxdepth 4 -path '*/scripts/package_remote_diagnostic_app.py' -print -quit)" || return $?
  [[ -n "$source" ]] || { echo "BLOCKED: source package missing"; return 2; }
  local root
  root="$(dirname "$(dirname "$source")")"

  (cd "$root" && python3 scripts/package_remote_diagnostic_app.py) || return $?
  local archive="$root/dist/genvex-nabto-remote-local-app-source.tar.gz"
  local sums="$root/dist/APP_SOURCE_SHA256SUMS"
  (cd "$root/dist" && sha256sum --check --status APP_SOURCE_SHA256SUMS) || return $?
  [[ -f "$archive" && -f "$sums" ]] || return 2
  local digest
  digest="$(sha256sum "$archive" | cut -d ' ' -f 1)" || return $?
  (cd "$root" && python3 scripts/dev4_upgrade_transaction.py --validate-archive "$archive" "$digest") || return $?
  echo "ARCHIVE_PACKAGE: VERIFIED"

  REMOTE_DIR="$(ssh_cmd 'umask 077; mktemp -d /mnt/data/supervisor/apps/local/.genvex-dev4-transfer.XXXXXX')" || return $?
  [[ "$REMOTE_DIR" =~ ^/mnt/data/supervisor/apps/local/\.genvex-dev4-transfer\.[A-Za-z0-9]+$ ]] || {
    echo "BLOCKED: unsafe transfer directory"
    return 2
  }

  for name in dev4_source_baseline_preflight.py dev4_upgrade_transaction.py; do
    ssh_cmd "sh -c 'umask 077; cat > \"$REMOTE_DIR/$name\"'" \
      <"$root/scripts/$name" || return $?
  done
  ssh_cmd "sh -c 'umask 077; cat > \"$REMOTE_DIR/source.tar.gz\"'" \
    <"$archive" || return $?
  echo "TRANSFER_STAGED: PASS"

  ssh_cmd "python3 '$REMOTE_DIR/dev4_upgrade_transaction.py' --diagnose-archive '$REMOTE_DIR/source.tar.gz' '$digest'" || return $?
  ssh_cmd "python3 '$REMOTE_DIR/dev4_upgrade_transaction.py' --validate-archive '$REMOTE_DIR/source.tar.gz' '$digest'" || return $?
  ssh_cmd "python3 '$REMOTE_DIR/dev4_source_baseline_preflight.py' --execute-readonly" || return $?
  echo "PREFLIGHT: PASS"

  if [[ "$MODE" == "--preflight" ]]; then
    echo "DEV4_UPGRADE_RESULT: PREFLIGHT_PASS"
    return 0
  fi
  ssh_cmd "python3 '$REMOTE_DIR/dev4_upgrade_transaction.py' --apply '$REMOTE_DIR/source.tar.gz' '$digest'" || return $?
  echo "DEV4_UPGRADE_OPERATOR: COMPLETE"
}

if run >"$OUT" 2>&1; then
  RC=0
else
  RC=$?
fi
clear
echo "===== DEV4 UPGRADE RESULT ====="
cat "$OUT"
echo "STEAM_DECK_EXIT_CODE: $RC"
exit "$RC"
