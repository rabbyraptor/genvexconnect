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
  printf '%s\n' '===== DEV9 SYNCHRONIZED RPC42/RPC45 LIVE PROBE ====='
  [[ ! -f "$LOG" ]] || cat "$LOG"
  printf 'RPC42_EXIT_CODE: %s\n' "$EXIT_CODE"
  rm -rf -- "$TMP"
}
trap finish EXIT

BASE="https://raw.githubusercontent.com/rabbyraptor/genvexconnect/$PIN"
for file in \
  scripts/probe_rpc42_rpc45_sync_readonly.py \
  tests/fixtures/candidate_readonly_query42.xml \
  tests/fixtures/candidate_readonly_query45.xml
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

# Read directly from controlling terminal to avoid silent noninteractive EOF.
prompt_tty() {
  local label="$1" name="$2" reply
  if [[ ! -r /dev/tty ]]; then
    echo "RPC42_INPUT_ERROR: INTERACTIVE_TTY_REQUIRED" >> "$LOG"
    return 2
  fi
  printf "%s" "$label" >/dev/tty
  if ! IFS= read -r reply </dev/tty; then
    echo "RPC42_INPUT_ERROR: INPUT_CANCELLED" >> "$LOG"
    return 2
  fi
  printf -v "$name" "%s" "$reply"
}
if [[ -z "$GENVEX_NABTO_IDENTITY" ]]; then
  echo "INPUT_STAGE: NABTO_IDENTITY" >> "$LOG"
  prompt_tty "Nabto identity (email): " GENVEX_NABTO_IDENTITY || { EXIT_CODE=2; exit "$EXIT_CODE"; }
fi
if [[ -z "$GENVEX_NABTO_HOST" ]]; then
  echo "INPUT_STAGE: NABTO_HOST" >> "$LOG"
  prompt_tty "Device hostname (label.remote.lscontrol.dk): " GENVEX_NABTO_HOST || { EXIT_CODE=2; exit "$EXIT_CODE"; }
fi
export GENVEX_NABTO_IDENTITY GENVEX_NABTO_HOST
{
  [[ -n "$GENVEX_NABTO_IDENTITY" ]] && echo "RPC42_IDENTITY_INPUT: PRESENT" || echo "RPC42_IDENTITY_INPUT: MISSING"
  [[ -n "$GENVEX_NABTO_HOST" ]] && echo "RPC42_HOST_INPUT: PRESENT" || echo "RPC42_HOST_INPUT: MISSING"
} >> "$LOG"

if python3 "$TMP/scripts/probe_rpc42_rpc45_sync_readonly.py" >> "$LOG" 2>&1; then
  EXIT_CODE=0
else
  EXIT_CODE=$?
fi
exit "$EXIT_CODE"
