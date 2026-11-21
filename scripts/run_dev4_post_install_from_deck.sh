#!/usr/bin/env bash
# DEV4 P.5: installed App, five HA entities, preserved DEV3 source and backup.
# Read-only; no upgrade, start, stop, credential access or SDK traffic.
set -euo pipefail
umask 077
if [[ $# -ne 0 ]]; then
  echo "Usage: bash run_dev4_post_install_from_deck.sh" >&2
  exit 2
fi

PIN="1925bf295f5eeaebd049b6bf5d106ec384f2f99e"
HOST="root@rabbyshome.duckdns.org"
PORT=22222
WORK="$(mktemp -d /tmp/genvex-dev4-p5.XXXXXX)"
RESULT="$WORK/results.txt"
REMOTE_DIR=""

ssh_remote() {
  ssh -T -p "$PORT" -o BatchMode=yes -o ServerAliveInterval=30 "$HOST" "$@"
}

cleanup() {
  if [[ -n "$REMOTE_DIR" && "$REMOTE_DIR" =~ ^/tmp/genvex-dev4-p5\.[a-zA-Z0-9]+$ ]]; then
    ssh_remote "rm -rf -- '$REMOTE_DIR'" </dev/null >/dev/null 2>&1 || true
  fi
  rm -rf -- "$WORK"
}
trap cleanup EXIT

run_gate() {
  echo "===== DEV4 GATE P.5 ====="
  echo "SOURCE_COMMIT: $PIN"
  for name in dev4_source_baseline_preflight.py dev4_post_install_verify.py; do
    curl --fail --silent --show-error --location --max-time 45 \
      "https://raw.githubusercontent.com/rabbyraptor/genvexconnect/$PIN/scripts/$name" \
      -o "$WORK/$name" || return $?
    python3 -m py_compile "$WORK/$name" || return $?
  done
  echo "SCRIPT_COMPILE: PASS"
  REMOTE_DIR="$(ssh_remote 'umask 077; mktemp -d /tmp/genvex-dev4-p5.XXXXXX')" || return $?
  [[ "$REMOTE_DIR" =~ ^/tmp/genvex-dev4-p5\.[a-zA-Z0-9]+$ ]] || {
    echo "BLOCKED: STAGING_PATH"
    return 2
  }
  for name in dev4_source_baseline_preflight.py dev4_post_install_verify.py; do
    ssh_remote "sh -c 'umask 077; cat > \"$REMOTE_DIR/$name\"'" \
      <"$WORK/$name" || return $?
  done
  echo "READONLY_SCRIPT_STAGED: PASS"
  ssh_remote "python3 '$REMOTE_DIR/dev4_post_install_verify.py' --execute-readonly" || return $?
}

if run_gate >"$RESULT" 2>&1; then
  RC=0
else
  RC=$?
fi
clear
echo "===== DEV4 P.5 POST-INSTALL RESULT ====="
cat "$RESULT"
echo "STEAM_DECK_EXIT_CODE: $RC"
exit "$RC"
