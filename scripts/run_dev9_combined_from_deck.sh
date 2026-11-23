#!/usr/bin/env bash
# DEV9 combined App+HA source package: single pinned transfer and installer.
# Run on the operator's trusted Steam Deck SSH client.
set -euo pipefail
umask 077

if [[ $# != 2 || ( "$1" != "--preflight" && "$1" != "--apply" )
      || ! "$2" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Usage: run_dev9_combined_from_deck.sh --preflight|--apply <pinned-source-commit>" >&2
  exit 2
fi
MODE="$1"
COMMIT="$2"
TRUSTED_HOST="rabbyshome.duckdns.org"
TARGET_HOST="${GENVEX_HAOS_HOST:-$TRUSTED_HOST}"
HOST="root@$TARGET_HOST"
PORT=22222

WORK=$(mktemp -d /tmp/genvex-dev9-release.XXXXXX)
RESULT="$WORK/result.txt"
REMOTE=""
SSH_EXTRA=()

prepare_ssh() {
  if [[ "$TARGET_HOST" == "$TRUSTED_HOST" ]]; then
    echo "SSH_TARGET: trusted:$TRUSTED_HOST:$PORT"
    return 0
  fi
  if [[ ! "$TARGET_HOST" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]]; then
    echo "SSH_TARGET_INVALID"
    return 2
  fi
  local pinned="$WORK/pinned_known_hosts" source_file
  : > "$pinned"
  for source_file in "$HOME/.ssh/known_hosts" "$HOME/.ssh/known_hosts2"; do
    [[ -f "$source_file" ]] || continue
    ssh-keygen -F "[$TRUSTED_HOST]:$PORT" -f "$source_file" 2>/dev/null |
      awk -v target="[$TARGET_HOST]:$PORT" \
        '$1 !~ /^#/ && $3 != "" && ($2 ~ /^ssh-/ || $2 ~ /^ecdsa-sha2-/) {
          print target, $2, $3
        }' >> "$pinned" || true
  done
  if [[ ! -s "$pinned" ]]; then
    echo "SSH_TRUST_PIN_MISSING"
    return 2
  fi
  sort -u "$pinned" -o "$pinned"
  SSH_EXTRA=(
    -o "UserKnownHostsFile=$pinned"
    -o "GlobalKnownHostsFile=/dev/null"
    -o StrictHostKeyChecking=yes
    -o CheckHostIP=no
  )
  echo "SSH_TARGET: local IPv4 with previously trusted host key"
}

ssh_cmd() {
  ssh -T -p "$PORT" -o BatchMode=yes -o ConnectTimeout=6 \
      -o ConnectionAttempts=5 -o ServerAliveInterval=30 \
      "${SSH_EXTRA[@]}" "$HOST" "$@"
}

cleanup() {
  if [[ "$REMOTE" =~ ^/mnt/data/supervisor/apps/local/\.genvex-dev9-transfer\.[A-Za-z0-9]+$ ]]; then
    ssh_cmd "rm -rf -- '$REMOTE'" </dev/null >/dev/null 2>&1 || true
  fi
  rm -rf -- "$WORK"
}
trap cleanup EXIT

execute() {
  echo "===== GENVEX DEV9 COMBINED RELEASE ====="
  echo "MODE: $MODE"
  echo "SOURCE_COMMIT: $COMMIT"
  prepare_ssh || return $?

  curl -fsSL --retry 3 --max-time 120 \
    "https://codeload.github.com/rabbyraptor/genvexconnect/tar.gz/$COMMIT" \
    -o "$WORK/checkout.tar.gz"
  mkdir "$WORK/source"
  tar -xzf "$WORK/checkout.tar.gz" -C "$WORK/source"
  local root
  root=$(find "$WORK/source" -mindepth 1 -maxdepth 1 -type d -print -quit)
  [[ -n "$root" && -f "$root/scripts/package_dev9_combined.py"
    && -f "$root/scripts/install_dev9_combined.py" ]] || return 2

  (cd "$root" && python3 scripts/package_dev9_combined.py)
  local source_archive="$root/dist/genvex-remote-dev9-combined.tar.gz"
  (cd "$root/dist" && sha256sum -c --status DEV9_COMBINED_SHA256SUMS)
  local sha
  sha=$(sha256sum "$source_archive" | cut -d ' ' -f 1)
  [[ "$sha" =~ ^[0-9a-f]{64}$ ]] || return 2

  REMOTE=$(ssh_cmd \
    'umask 077; mktemp -d /mnt/data/supervisor/apps/local/.genvex-dev9-transfer.XXXXXX')
  [[ "$REMOTE" =~ ^/mnt/data/supervisor/apps/local/\.genvex-dev9-transfer\.[A-Za-z0-9]+$ ]] || return 2

  ssh_cmd "sh -c 'umask 077; cat > \"$REMOTE/release.tar.gz\"'" \
    < "$source_archive"
  ssh_cmd "sh -c 'umask 077; cat > \"$REMOTE/install.py\"'" \
    < "$root/scripts/install_dev9_combined.py"
  echo "SINGLE_SOURCE_PACKAGE_TRANSFER: PASS"
  echo "RELEASE_SHA256: $sha"

  ssh_cmd "python3 '$REMOTE/install.py' --preflight '$REMOTE/release.tar.gz' '$sha'"
  if [[ "$MODE" == "--preflight" ]]; then
    echo "DEV9_OPERATOR_GATE: PREFLIGHT_PASS"
    return 0
  fi

  ssh_cmd "python3 '$REMOTE/install.py' --apply '$REMOTE/release.tar.gz' '$sha'"
  echo "DEV9_OPERATOR_GATE: INSTALLED"
}

RC=0
execute >"$RESULT" 2>&1 || RC=$?
printf '\033[3J\033[2J\033[H'
echo "===== GENVEX DEV9 RELEASE RESULT ====="
cat "$RESULT"
echo "STEAM_DECK_EXIT_CODE: $RC"
exit "$RC"
