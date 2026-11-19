#!/usr/bin/env bash
# Transfer *encrypted* existing Nabto profile transiently from Steam Deck
# and run exactly one five-sensor read-only RPC 45 under QEMU in HAOS test addon.
# Needs: working key-based SSH into HAOS host with docker exec access,
#        rebuilt and running genvex_nabto_runtime_test version 0.4.0.
set -euo pipefail
umask 077

PROFILE="${HOME}/.local/share/genvex-nabto-profile-1024-test"
CONTAINER="app_local_genvex_nabto_runtime_test"
[[ -r "${PROFILE}/client.crt" && -r "${PROFILE}/client-encrypted.key" ]] || {
  echo "Missing existing Steam Deck encrypted test identity." >&2
  exit 2
}

read -r -p "HAOS SSH target (same user@host as previous test): " SSH_TARGET
[[ "$SSH_TARGET" =~ ^[A-Za-z0-9_.@:-]+$ ]] || {
  echo "Invalid SSH target syntax." >&2
  exit 2
}
read -r -p "Nabto identity (email): " IDENTITY
read -r -p "Gateway Nabto hostname: " HOST
[[ "$IDENTITY" == *"@"* && "$HOST" =~ ^[A-Za-z0-9.-]+$ ]] || {
  echo "Invalid account/host." >&2
  exit 2
}

# Key auth is required for noninteractive tar transfer; never echo secrets.
echo "Checking isolated HAOS addon..."
ssh -T "$SSH_TARGET" "docker exec $CONTAINER test -f /opt/nabto/probe_remote_batch.py && docker exec $CONTAINER test -x /opt/x86_64-sysroot/usr/local/bin/python3" </dev/null || {
  echo "HAOS addon v0.4.0 not running/built, or SSH/docker access unavailable." >&2
  exit 3
}

REMOTE_DIR="$(ssh -T "$SSH_TARGET" "docker exec $CONTAINER mktemp -d /tmp/genvex-haos-batch.XXXXXX" </dev/null | tr -d '\r\n')"
[[ "$REMOTE_DIR" =~ ^/tmp/genvex-haos-batch\.[A-Za-z0-9]+$ ]] || {
  echo "Invalid isolated remote directory: abort." >&2
  exit 3
}

cleanup() {
  ssh -T "$SSH_TARGET" "docker exec $CONTAINER rm -rf '$REMOTE_DIR'" </dev/null >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Transferring existing encrypted key and public cert into temporary test directory..."
tar -C "$PROFILE" -cf - client.crt client-encrypted.key |
  ssh -T "$SSH_TARGET" "docker exec -i $CONTAINER tar -xf - -C '$REMOTE_DIR'"
ssh -T "$SSH_TARGET" "docker exec $CONTAINER chmod 700 '$REMOTE_DIR'; docker exec $CONTAINER chmod 600 '$REMOTE_DIR/client.crt' '$REMOTE_DIR/client-encrypted.key'" </dev/null

echo
echo "The passphrase will not echo or be passed in process arguments."
IFS= read -r -s -p "Existing encrypted key passphrase: " PASSPHRASE </dev/tty
echo

# Pipe one JSON line through SSH/stdin, never in shell args nor environment.
# Avoid passing account/hostname via remote command line.
echo "Running one authenticated read-only remote RPC 45 batch through HAOS QEMU..."
{
  printf '%s\n%s\n%s\n' "$IDENTITY" "$HOST" "$PASSPHRASE" |
    python3 -c 'import json,sys; i,h,p=(sys.stdin.readline().rstrip("\n") for _ in range(3)); print(json.dumps({"identity":i,"host":h,"passphrase":p}))'
} |
  ssh -T "$SSH_TARGET" "docker exec -i -e GENVEX_NABTO_PROFILE='$REMOTE_DIR' $CONTAINER /usr/local/bin/qemu-x86_64-static -L /opt/x86_64-sysroot -E LD_LIBRARY_PATH=/opt/x86_64-sysroot/usr/local/lib /opt/x86_64-sysroot/usr/local/bin/python3 /opt/nabto/probe_remote_batch.py --settings-stdin"

unset PASSPHRASE
echo "HAOS remote batch test finished."
