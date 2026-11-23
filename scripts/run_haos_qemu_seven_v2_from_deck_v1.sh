#!/usr/bin/env bash
# Operator-initiated, ONE seven-address read-only RPC45 under HAOS QEMU.
# Run on Steam Deck, not HAOS host. Default: inert preflight.
# Existing encrypted profile is copied transiently; never persist credentials.
set -euo pipefail
umask 077

PIN="3c7506bfeeaef869e71b113d5009c23cc9918a6a"
APP="app_local_genvex_nabto_runtime_test"
PROFILE="$HOME/.local/share/genvex-nabto-profile-1024-test"
PROBE_PATH="experimental/genvex_remote/probe_remote_snapshot_v2.py"
MODE="${1:---preflight}"
if (( $# > 1 )) || [[ "$MODE" != "--preflight" && "$MODE" != "--execute-live" ]]; then
  echo "Usage: bash $0 [--preflight|--execute-live]" >&2
  exit 2
fi
echo "===== HAOS QEMU SEVEN-ADDRESS V2: $MODE ====="
echo "Pinned public probe source: $PIN"
echo "Read-only RPC45: 20,21,22,23,26,18,19; one invocation; no retries."
echo "No installed App, Core, or LAN component modification."
if [[ "$MODE" == "--preflight" ]]; then
  echo "PASS: inert preview; no SSH, SDK, credentials or RPC."
  exit 0
fi

[[ -r "$PROFILE/client.crt" && -r "$PROFILE/client-encrypted.key" ]] || {
  echo "Missing existing encrypted test profile" >&2; exit 2;
}
command -v ssh >/dev/null
command -v curl >/dev/null
command -v tar >/dev/null
read -r -p "HAOS SSH target (user@host): " TARGET
read -r -p "SSH port [22222]: " PORT
PORT="${PORT:-22222}"
[[ "$PORT" =~ ^[0-9]{1,5}$ ]] && (( 10#$PORT >= 1 && 10#$PORT <= 65535 )) || {
  echo "Invalid SSH port" >&2; exit 2;
}
[[ "$TARGET" =~ ^[A-Za-z0-9_.-]+@[A-Za-z0-9_.:-]+$ ]] || {
  echo "Invalid SSH target" >&2; exit 2;
}
read -r -p "Nabto identity (email, visible): " IDENTITY
read -r -p "Gateway device ID (12 digits, visible): " DEVICE
[[ "$IDENTITY" == *"@"* && "$IDENTITY" != *$'\n'* && "$IDENTITY" != *$'\r'* && "$DEVICE" =~ ^[0-9]{12}$ ]] || {
  echo "Invalid identity or device ID" >&2; exit 2;
}
HOST="${DEVICE}.remote.lscontrol.dk"
unset DEVICE

# Preflight remote SDK and public probe prerequisites BEFORE prompting for key.
SSH=(ssh -T -p "$PORT" -o BatchMode=yes -o ConnectTimeout=10 "$TARGET")
"${SSH[@]}" "docker exec $APP test -f /opt/nabto/libnabto_client_api.so && docker exec $APP test -x /opt/x86_64-sysroot/usr/local/bin/python3 && docker exec $APP test -x /usr/local/bin/qemu-x86_64-static" </dev/null || {
  echo "Missing isolated HAOS QEMU/SDK test prerequisites" >&2; exit 3;
}

TMP="$(mktemp -d /tmp/genvex-haos-v2-seven.XXXXXX)"
REMOTE=""
cleanup() {
  unset PASSPHRASE IDENTITY HOST
  if [[ -n "$REMOTE" && "$REMOTE" =~ ^/tmp/genvex-haos-seven\.[A-Za-z0-9]+$ ]]; then
    "${SSH[@]}" "docker exec $APP rm -rf '$REMOTE'" </dev/null >/dev/null 2>&1 || echo "WARNING: remote temporary cleanup failed; inspect isolated App." >&2
  fi
  rm -rf -- "$TMP"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "Fetching pinned public seven-address probe (not from a moving branch)..."
curl -fsSL --max-time 30 \
  "https://raw.githubusercontent.com/rabbyraptor/genvexconnect/$PIN/$PROBE_PATH" \
  -o "$TMP/probe_remote_snapshot_v2.py"
python3 -m py_compile "$TMP/probe_remote_snapshot_v2.py"
REMOTE="$("${SSH[@]}" "docker exec $APP mktemp -d /tmp/genvex-haos-seven.XXXXXX" </dev/null | tr -d '\r\n')"
[[ "$REMOTE" =~ ^/tmp/genvex-haos-seven\.[A-Za-z0-9]+$ ]] || {
  REMOTE=""; echo "Invalid temporary App directory" >&2; exit 3;
}

# Files go into the temporary isolated App directory; no installed App path writes.
tar -C "$PROFILE" -cf - client.crt client-encrypted.key |
  "${SSH[@]}" "docker exec -i $APP tar -xf - -C '$REMOTE'"
tar -C "$TMP" -cf - probe_remote_snapshot_v2.py |
  "${SSH[@]}" "docker exec -i $APP tar -xf - -C '$REMOTE'"
"${SSH[@]}" "docker exec $APP chmod 700 '$REMOTE' && docker exec $APP chmod 600 '$REMOTE/client.crt' '$REMOTE/client-encrypted.key' '$REMOTE/probe_remote_snapshot_v2.py' && docker exec $APP test -f '$REMOTE/probe_remote_snapshot_v2.py'" </dev/null

echo "A single live read-only Nabto RPC45 will now run under QEMU."
IFS= read -r -s -p "Encrypted test-key passphrase (hidden): " PASSPHRASE </dev/tty
printf '\n'
[[ -n "$PASSPHRASE" && "${#PASSPHRASE}" -le 1000 && "$PASSPHRASE" != *$'\n'* ]] || {
  echo "Invalid passphrase" >&2; exit 2;
}

# Serialize only to stdin, not shell argv/environment. Profile remains encrypted.
# timeout limits one QEMU process; exit code and sanitized diagnostic remain visible.
set +e
printf '%s\n%s\n%s\n' "$IDENTITY" "$HOST" "$PASSPHRASE" |
  python3 -c 'import json,sys; a=[sys.stdin.readline().rstrip("\n") for _ in range(3)]; sys.stdout.write(json.dumps(dict(zip(("identity","host","passphrase"),a)))+"\n")' |
  "${SSH[@]}" "docker exec -i -e GENVEX_NABTO_PROFILE='$REMOTE' $APP timeout -s TERM -k 5 90 /usr/local/bin/qemu-x86_64-static -L /opt/x86_64-sysroot -E LD_LIBRARY_PATH=/opt/x86_64-sysroot/usr/local/lib /opt/x86_64-sysroot/usr/local/bin/python3 '$REMOTE/probe_remote_snapshot_v2.py' --settings-stdin"
RC=$?
set -e
unset PASSPHRASE
echo "Single v2 QEMU probe exit status: $RC"
exit "$RC"
