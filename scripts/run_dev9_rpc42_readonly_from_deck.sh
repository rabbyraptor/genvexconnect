#!/usr/bin/env bash
# One read-only RPC42 Optima 270 test with an existing Nabto 4 Deck profile.
# Fetches source-only code pinned to a public staging commit, no Git auth.
set -euo pipefail
umask 077

PIN="${1:-}"
[[ "$PIN" =~ ^[0-9a-f]{40}$ ]] || { printf 'MISSING_PINNED_SOURCE_SHA\n' >&2; exit 2; }

TMP="$(mktemp -d /tmp/genvex-rpc42-read.XXXXXXXX)"
LOG="$TMP/verify.log"
EXIT_CODE=0
finish() {
  printf '\033[3J\033[2J\033[H'
  printf '%s\n' '===== DEV9 RPC42 READ-ONLY LIVE PROBE ====='
  [[ ! -f "$LOG" ]] || cat "$LOG"
  printf 'RPC42_EXIT_CODE: %s\n' "$EXIT_CODE"
  rm -rf -- "$TMP"
}
trap finish EXIT

BASE="https://raw.githubusercontent.com/rabbyraptor/genvexconnect/$PIN"
for file in \
  scripts/probe_remote_setpoint42_readonly.py \
  scripts/reconstruct_rpc42_readonly.py \
  tests/fixtures/candidate_readonly_query42.xml \
  docs/references/optima270_micro_nabto_setpoint_catalog.json
do
  mkdir -p "$TMP/$(dirname "$file")"
  if ! curl -fsSL --retry 3 --connect-timeout 15 --max-time 45 \
        "$BASE/$file" -o "$TMP/$file"; then
    echo "RPC42_SOURCE_FETCH_FAILED: $file" >"$LOG"
    EXIT_CODE=2
    exit "$EXIT_CODE"
  fi
done
if ! python3 -m py_compile "$TMP/scripts/"*.py; then
  echo 'RPC42_PYTHON_PREFLIGHT: FAIL' >"$LOG"
  EXIT_CODE=2
  exit "$EXIT_CODE"
fi

export GENVEX_NABTO_IDENTITY="${GENVEX_NABTO_IDENTITY:-}"
export GENVEX_NABTO_HOST="${GENVEX_NABTO_HOST:-}"
if [[ -z "$GENVEX_NABTO_IDENTITY" ]]; then
  read -r -s -p 'Nabto client identity (email, input hidden): ' GENVEX_NABTO_IDENTITY
  printf '\n'
fi
if [[ -z "$GENVEX_NABTO_HOST" ]]; then
  read -r -s -p 'Device hostname (12-digit ID.remote.lscontrol.dk, input hidden): ' GENVEX_NABTO_HOST
  printf '\n'
fi
export GENVEX_NABTO_IDENTITY GENVEX_NABTO_HOST

if ! python3 "$TMP/scripts/reconstruct_rpc42_readonly.py" --address 7 > "$LOG" 2>&1; then
  EXIT_CODE=2
  exit "$EXIT_CODE"
fi
if python3 "$TMP/scripts/probe_remote_setpoint42_readonly.py" >> "$LOG" 2>&1; then
  EXIT_CODE=0
else
  EXIT_CODE=$?
fi
exit "$EXIT_CODE"
