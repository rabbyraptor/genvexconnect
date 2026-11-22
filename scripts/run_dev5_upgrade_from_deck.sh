#!/usr/bin/env bash
# Pinned, source-only DEV4 -> DEV5 update from Steam Deck.
# --preflight stages a temporary archive but does not stop or update the App.
# --apply invokes the separately gated source swap and Supervisor backup/update.
set -euo pipefail
umask 077

if [[ $# != 2 || ( "$1" != "--preflight" && "$1" != "--apply" )
      || ! "$2" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Usage: bash run_dev5_upgrade_from_deck.sh --preflight|--apply <40-char-commit>" >&2
  exit 2
fi

MODE="$1"
SOURCE_COMMIT="$2"
HOST="root@rabbyshome.duckdns.org"
PORT=22222
WORK=$(mktemp -d /tmp/genvex-dev5-upgrade.XXXXXX)
OUT="$WORK/output.log"
REMOTE_DIR=""

ssh_cmd() {
  ssh -T -p "$PORT" -o BatchMode=yes -o ServerAliveInterval=30 "$HOST" "$@"
}

cleanup() {
  if [[ "$REMOTE_DIR" =~ ^/mnt/data/supervisor/apps/local/\.genvex-dev5-transfer\.[A-Za-z0-9]+$ ]]; then
    ssh_cmd "rm -rf -- '$REMOTE_DIR'" </dev/null >/dev/null 2>&1 || true
  fi
  rm -rf -- "$WORK"
}
trap cleanup EXIT

run() {
  echo "===== DEV5 VERSIONED UPDATE ====="
  echo "MODE: $MODE"
  echo "SOURCE_COMMIT: $SOURCE_COMMIT"

  curl --fail --silent --show-error --location --max-time 120 \
    "https://codeload.github.com/rabbyraptor/genvexconnect/tar.gz/$SOURCE_COMMIT" \
    --output "$WORK/checkout.tar.gz"

  mkdir -p "$WORK/source"
  tar -xzf "$WORK/checkout.tar.gz" -C "$WORK/source"
  local root
  root=$(find "$WORK/source" -mindepth 1 -maxdepth 1 -type d -print -quit)
  [[ -n "$root" && -f "$root/scripts/dev5_upgrade_transaction.py" ]] || return 2

  (cd "$root" && python3 scripts/package_remote_diagnostic_app.py)
  local archive="$root/dist/genvex-nabto-remote-local-app-source.tar.gz"
  (cd "$root/dist" && sha256sum -c --status APP_SOURCE_SHA256SUMS)
  local digest
  digest=$(sha256sum "$archive" | cut -d ' ' -f 1)
  [[ "$digest" =~ ^[0-9a-f]{64}$ ]] || return 2
  echo "SOURCE_PACKAGE_SHA256: $digest"

  REMOTE_DIR=$(ssh_cmd \
    'umask 077; mktemp -d /mnt/data/supervisor/apps/local/.genvex-dev5-transfer.XXXXXX')
  [[ "$REMOTE_DIR" =~ ^/mnt/data/supervisor/apps/local/\.genvex-dev5-transfer\.[A-Za-z0-9]+$ ]] || return 2

  ssh_cmd "sh -c 'umask 077; cat > \"$REMOTE_DIR/source.tar.gz\"'" < "$archive"
  ssh_cmd "sh -c 'umask 077; cat > \"$REMOTE_DIR/dev5_upgrade_transaction.py\"'" \
    < "$root/scripts/dev5_upgrade_transaction.py"
  echo "TEMPORARY_TRANSFER: PASS"

  ssh_cmd "python3 '$REMOTE_DIR/dev5_upgrade_transaction.py' --validate-archive '$REMOTE_DIR/source.tar.gz' '$digest'"
  ssh_cmd "python3 '$REMOTE_DIR/dev5_upgrade_transaction.py' --preflight '$REMOTE_DIR/source.tar.gz' '$digest'"
  echo "STAGED_PREFLIGHT: PASS"

  if [[ "$MODE" == "--preflight" ]]; then
    echo "DEV5_OPERATOR_RESULT: PREFLIGHT_PASS"
    return 0
  fi
  echo "SUPERVISOR_SOURCE_UPDATE: REQUESTED"
  ssh_cmd "python3 '$REMOTE_DIR/dev5_upgrade_transaction.py' --apply '$REMOTE_DIR/source.tar.gz' '$digest'"
  echo "DEV5_OPERATOR_RESULT: APPLIED_STOPPED"
}

if run > "$OUT" 2>&1; then
  RC=0
else
  RC=$?
fi
printf '\033[3J\033[2J\033[H'
echo "===== DEV5 UPGRADE OPERATOR RESULT ====="
cat "$OUT"
echo "STEAM_DECK_EXIT_CODE: $RC"
exit "$RC"
