#!/usr/bin/env bash
# Steam Deck runner for ONE Optima270 RPC45 source-defined candidate.
# Default is OFFLINE preflight. No SDK, profile or network until --execute-live.
set -euo pipefail
umask 077

ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PROBE="$ROOT/scripts/probe_optima270_single_source_candidate.py"
KEY=frost_protection_temp

usage() {
  echo "Usage: bash scripts/run_optima270_one_read_from_deck.sh [--preflight|--execute-live]"
}

mode="${1:---preflight}"
if [[ $# -gt 1 ]] || [[ "$mode" != --preflight && "$mode" != --execute-live ]]; then
  usage >&2
  exit 2
fi

[[ -f "$PROBE" ]] || { echo "FAIL: probe script not found"; exit 2; }
command -v python3 >/dev/null || { echo "FAIL: python3 unavailable"; exit 2; }
command -v timeout >/dev/null || { echo "FAIL: timeout utility unavailable"; exit 2; }
python3 -m py_compile "$PROBE"
echo "===== 2B OFFLINE PREFLIGHT ====="
python3 "$PROBE" --key "$KEY"
if [[ "$mode" == --preflight ]]; then
  echo "PASS: preview complete; no Nabto session was opened"
  exit 0
fi

PROFILE="$HOME/.local/share/genvex-nabto-profile-1024-test"
LIB="$HOME/genvex-ca-check/libnabto_client_api.so"
for file in "$PROFILE/client.crt" "$PROFILE/client-encrypted.key" "$LIB"; do
  if [[ ! -f "$file" || ! -r "$file" || -L "$file" ]]; then
    echo "FAIL: existing authorized profile or SDK library unavailable" >&2
    exit 2
  fi
done
echo "PASS: existing test profile and SDK files are present"

# Never echo the account, hostname, device ID, or encrypted-key passphrase.
IFS= read -r -s -p "Nabto-identitet (e-mail; skjult): " GENVEX_NABTO_IDENTITY || exit 2
printf '\n'
IFS= read -r -s -p "Genvex device-ID (12 cifre; skjult): " DEVICE_ID || exit 2
printf '\n'
if [[ ! "$DEVICE_ID" =~ ^[0-9]{12}$ ]]; then
  echo "FAIL: device ID must be exactly 12 ASCII digits" >&2
  exit 2
fi
# The previously successful phase-1 scripts accepted the *full* known host.
# Ask for that same full host independently and compare locally, without
# logging or printing either the ID or the host.
IFS= read -r -s -p "Tidligere fungerende Nabto-hostnavn (skjult): " KNOWN_HOST || exit 2
printf '\\n'
if [[ ! "$KNOWN_HOST" =~ ^[0-9]{12}\.remote\.lscontrol\.dk$ ]]; then
  echo "FAIL: known gateway hostname format invalid" >&2
  unset DEVICE_ID KNOWN_HOST
  exit 2
fi
if [[ "$KNOWN_HOST" != "${DEVICE_ID}.remote.lscontrol.dk" ]]; then
  echo "FAIL: device ID does not match the previously working gateway hostname; no RPC will be sent" >&2
  unset DEVICE_ID KNOWN_HOST
  exit 2
fi
echo "PASS: device ID matches independently entered known working hostname"
export GENVEX_NABTO_IDENTITY
export GENVEX_NABTO_HOST="$KNOWN_HOST"
unset DEVICE_ID KNOWN_HOST

# Explicit shell prompt before starting a timed subprocess.
echo "Næste indtastning er adgangskoden til den eksisterende krypterede testnøgle."
IFS= read -r -s -p "Nøgleadgangskode (skjult): " PASSPHRASE || exit 2
printf '\n'
if [[ -z "$PASSPHRASE" || "${#PASSPHRASE}" -gt 1000 ]]; then
  echo "FAIL: empty or oversized key passphrase" >&2
  unset PASSPHRASE
  exit 2
fi
echo "PASS: input captured; launching one bounded read-only RPC45 test"

TEMP_ROOT="$(mktemp -d /tmp/genvex-rpc45-once.XXXXXX)"
if [[ ! "$TEMP_ROOT" =~ ^/tmp/genvex-rpc45-once\.[A-Za-z0-9]+$ ]]; then
  echo "FAIL: unsafe temporary directory" >&2
  unset PASSPHRASE
  exit 2
fi
cleanup() {
  unset PASSPHRASE GENVEX_NABTO_IDENTITY GENVEX_NABTO_HOST
  rm -rf -- "$TEMP_ROOT"
}
trap cleanup EXIT

export TMPDIR="$TEMP_ROOT"
# Passphrase is piped to stdin, NOT placed in CLI args or environment.
# Parent cleanup removes temporary key copies even if Python is killed.
set +e
printf '%s\n' "$PASSPHRASE" |
  timeout -k 5s 90s \
    python3 -u "$PROBE" \
      --key "$KEY" \
      --execute-live \
      --approved-read-only \
      --passphrase-stdin
result=$?
set -e
unset PASSPHRASE
if [[ "$result" -eq 124 ]]; then
  echo "FAIL: timed out after 90 seconds. No automatic retry; check emitted SDK stage."
elif [[ "$result" -eq 137 ]]; then
  echo "FAIL: probe forcibly killed. No automatic retry; cleanup is running."
elif [[ "$result" -eq 0 ]]; then
  echo "PASS: exactly one read-only candidate RPC45 probe completed"
else
  echo "FAIL: single-candidate probe returned status $result; no automatic retry."
fi
exit "$result"
