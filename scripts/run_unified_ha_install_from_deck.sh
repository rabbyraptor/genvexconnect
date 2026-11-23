#!/usr/bin/env bash
# Single pinned source/install/restart action for the Genvex Remote HA component.
# Does not alter the already-installed DEV6 Nabto App or persisted HA entries.
set -euo pipefail
umask 077

if [[ $# != 2 || "$1" != "--apply" || ! "$2" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Usage: bash run_unified_ha_install_from_deck.sh --apply <40-character-commit>" >&2
  exit 2
fi

PINNED_COMMIT="$2"
TRUSTED_NAME="rabbyshome.duckdns.org"
# Operator-set local address avoids public DuckDNS port refusal.
TARGET_HOST="${GENVEX_HAOS_HOST:-$TRUSTED_NAME}"
HOST="root@$TARGET_HOST"
PORT=22222
WORK=$(mktemp -d /tmp/genvex-unified-ha.XXXXXX)
OUT="$WORK/operator-result.log"
REMOTE_DIR=""
SSH_EXTRA=()

prepare_ssh_target() {
  if [[ "$TARGET_HOST" == "$TRUSTED_NAME" ]]; then
    echo "SSH_TARGET: hostname:$TARGET_HOST:$PORT"
    return 0
  fi
  if [[ ! "$TARGET_HOST" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]]; then
    echo "SSH_TARGET_INVALID: override requires literal IPv4" >&2
    return 2
  fi

  # Use only the *already trusted* DuckDNS host key. Never accept new
  # unverified IP host keys or disable strict SSH host key checking.
  local source_file pinned="$WORK/pinned_host_keys"
  : > "$pinned"
  for source_file in "$HOME/.ssh/known_hosts" "$HOME/.ssh/known_hosts2"; do
    [[ -f "$source_file" ]] || continue
    ssh-keygen -F "[$TRUSTED_NAME]:$PORT" -f "$source_file" 2>/dev/null |
      awk -v target="[$TARGET_HOST]:$PORT" \
        '$1 !~ /^#/ && $3 != "" && ($2 ~ /^ssh-/ || $2 ~ /^ecdsa-sha2-/) {
          print target, $2, $3
        }' >> "$pinned" || true
  done
  if [[ ! -s "$pinned" ]]; then
    echo "SSH_TRUST_PIN_MISSING: no previously trusted $TRUSTED_NAME:$PORT key in ~/.ssh/known_hosts" >&2
    return 2
  fi
  sort -u "$pinned" -o "$pinned"
  SSH_EXTRA=(
    -o "UserKnownHostsFile=$pinned"
    -o "GlobalKnownHostsFile=/dev/null"
    -o StrictHostKeyChecking=yes
    -o CheckHostIP=no
  )
  echo "SSH_TARGET: local:$TARGET_HOST:$PORT"
  echo "SSH_TRUST_PIN: PREVIOUSLY_VERIFIED_HOST_KEY"
}

ssh_cmd() {
  ssh -T -p "$PORT" -o BatchMode=yes -o ConnectTimeout=6 \
      -o ConnectionAttempts=5 -o ServerAliveInterval=30 \
      "${SSH_EXTRA[@]}" "$HOST" "$@"
}

cleanup() {
  if [[ "$REMOTE_DIR" =~ ^/mnt/data/supervisor/homeassistant/\.genvex-unified-transfer\.[A-Za-z0-9]+$ ]]; then
    ssh_cmd "rm -rf -- '$REMOTE_DIR'" </dev/null >/dev/null 2>&1 || true
  fi
  rm -rf -- "$WORK"
}
trap cleanup EXIT

run() {
  echo "===== UNIFIED GENVEX REMOTE HA INSTALL ====="
  echo "SOURCE_COMMIT: $PINNED_COMMIT"
  prepare_ssh_target || return $?

  curl --fail --silent --show-error --location --max-time 120 \
    "https://codeload.github.com/rabbyraptor/genvexconnect/tar.gz/$PINNED_COMMIT" \
    --output "$WORK/checkout.tar.gz" || return $?
  mkdir -p "$WORK/source"
  tar -xzf "$WORK/checkout.tar.gz" -C "$WORK/source" || return $?
  local source_root
  source_root=$(find "$WORK/source" -mindepth 1 -maxdepth 1 -type d -print -quit)
  [[ -n "$source_root" \
      && -f "$source_root/scripts/install_unified_ha_integration.py" \
      && -f "$source_root/experimental/home_assistant/custom_components/genvex_remote/manifest.json" ]] || return 2

  # Tar only regular .py/.json files, not directory entries or developer cache.
  SOURCE_ROOT="$source_root" WORK_ROOT="$WORK" python3 - <<'PY' || return $?
from pathlib import Path
import gzip, io, os, tarfile
source = Path(os.environ["SOURCE_ROOT"]) / "experimental/home_assistant/custom_components/genvex_remote"
target = Path(os.environ["WORK_ROOT"]) / "component.tar.gz"
files = sorted(p for p in source.rglob("*") if p.is_file() and p.suffix in (".py", ".json"))
if not 9 <= len(files) <= 40 or any(p.is_symlink() for p in files):
    raise SystemExit("Invalid HA component file set")
with target.open("wb") as stream:
    with gzip.GzipFile(filename="", fileobj=stream, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for path in files:
                arc = "genvex_remote/" + path.relative_to(source).as_posix()
                info = tar.gettarinfo(str(path), arcname=arc)
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mode = 0o644
                with path.open("rb") as content:
                    tar.addfile(info, content)
print("UNIFIED_COMPONENT_PACKAGED:", len(files))
PY

  local digest
  digest=$(sha256sum "$WORK/component.tar.gz" | cut -d ' ' -f 1)
  [[ "$digest" =~ ^[0-9a-f]{64}$ ]] || return 2
  echo "COMPONENT_SHA256: $digest"

  REMOTE_DIR=$(ssh_cmd 'umask 077; mktemp -d /mnt/data/supervisor/homeassistant/.genvex-unified-transfer.XXXXXX') || return $?
  [[ "$REMOTE_DIR" =~ ^/mnt/data/supervisor/homeassistant/\.genvex-unified-transfer\.[A-Za-z0-9]+$ ]] || return 2
  ssh_cmd "sh -c 'cat > \"$REMOTE_DIR/component.tar.gz\"'" \
    < "$WORK/component.tar.gz" || return $?
  ssh_cmd "sh -c 'cat > \"$REMOTE_DIR/install.py\"'" \
    < "$source_root/scripts/install_unified_ha_integration.py" || return $?
  echo "TRANSFER: PASS"

  ssh_cmd "python3 '$REMOTE_DIR/install.py' --apply '$REMOTE_DIR/component.tar.gz' '$digest'" || return $?
  echo "UNIFIED_OPERATOR_RESULT: PASS"
}

RC=0
run >"$OUT" 2>&1 || RC=$?
printf '\033[3J\033[2J\033[H'
echo "===== GENVEX UNIFIED HA RESULT ====="
cat "$OUT"
echo "STEAM_DECK_EXIT_CODE: $RC"
exit "$RC"
