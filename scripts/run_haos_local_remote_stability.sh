#!/bin/sh
# Local HAOS-host-only wrapper: two read-only RPC 45 batches in the
# installed v0.4.0 isolated test app. No SSH and no write RPCs.
set -eu
umask 077

CONTAINER="app_local_genvex_nabto_runtime_test"
AUTH_DIR="/mnt/data/supervisor/genvex-nabto-remote-profile"
DEVICE_ID="\${GENVEX_DEVICE_ID:-}"
IDENTITY="\${GENVEX_NABTO_IDENTITY:-}"

case "$DEVICE_ID" in
    ''|*[!0-9]*) echo "GENVEX_DEVICE_ID must be exactly 12 digits." >&2; exit 2 ;;
esac
if [ "\${#DEVICE_ID}" -ne 12 ]; then
    echo "GENVEX_DEVICE_ID must be exactly 12 digits." >&2
    exit 2
fi
case "$IDENTITY" in
    *@*.*) ;;
    *) echo "Set GENVEX_NABTO_IDENTITY to your registered Nabto identity." >&2; exit 2 ;;
esac
HOST="\${DEVICE_ID}.remote.lscontrol.dk"

for file in client.crt client-encrypted.key; do
    if [ ! -r "$AUTH_DIR/$file" ]; then
        echo "One-time encrypted profile provisioning required: $AUTH_DIR/$file" >&2
        echo "The earlier successful test kept these files on Steam Deck." >&2
        echo "No test run or credentials changed." >&2
        exit 3
    fi
done

docker exec "$CONTAINER" test -f /opt/nabto/probe_remote_batch.py
docker exec "$CONTAINER" test -x /opt/x86_64-sysroot/usr/local/bin/python3

REMOTE_DIR="$(docker exec "$CONTAINER" mktemp -d /tmp/genvex-haos-local.XXXXXX)"
case "$REMOTE_DIR" in
    /tmp/genvex-haos-local.*) ;;
    *) echo "Unexpected temporary path." >&2; exit 3 ;;
esac

SAVED_STTY=""
PASSPHRASE=""
cleanup() {
    if [ -n "$SAVED_STTY" ]; then
        stty "$SAVED_STTY" </dev/tty 2>/dev/null || true
    fi
    PASSPHRASE=""
    if [ -n "$REMOTE_DIR" ]; then
        docker exec "$CONTAINER" rm -rf "$REMOTE_DIR" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

tar -C "$AUTH_DIR" -cf - client.crt client-encrypted.key |
    docker exec -i "$CONTAINER" tar -xf - -C "$REMOTE_DIR"
docker exec "$CONTAINER" chmod 700 "$REMOTE_DIR"
docker exec "$CONTAINER" chmod 600 "$REMOTE_DIR/client.crt" "$REMOTE_DIR/client-encrypted.key"

SAVED_STTY="$(stty -g </dev/tty)"
printf "Encrypted Nabto key passphrase (hidden): " >/dev/tty
stty -echo </dev/tty
if ! IFS= read -r PASSPHRASE </dev/tty; then
    echo >&2
    echo "Passphrase input cancelled." >&2
    exit 3
fi
stty "$SAVED_STTY" </dev/tty
SAVED_STTY=""
printf '\n' >/dev/tty
[ -n "$PASSPHRASE" ] || { echo "Empty passphrase." >&2; exit 3; }

# Clear after reading input, immediately before the output heading.
printf '\033[2J\033[H'
echo "===== HAOS LOCAL NABTO STABILITY CHECK ====="
echo "Existing isolated HAOS/QEMU test app v0.4.0"
echo "Two read-only RPC 45 batches, five sensors each"
echo "Device ID: $DEVICE_ID"
echo "Endpoint: $HOST"
echo

TEST=1
while [ "$TEST" -le 2 ]; do
    echo "===== READ-ONLY BATCH $TEST / 2 ====="
    # Three stdin lines are JSON encoded by x86_64 Python, then handed
    # to the unmodified, verified read-only probe in the same process.
    # The passphrase is never placed in argv, environment or GitHub.
    {
        printf '%s\n' "$IDENTITY"
        printf '%s\n' "$HOST"
        printf '%s\n' "$PASSPHRASE"
    } |
        docker exec -i -e "GENVEX_NABTO_PROFILE=$REMOTE_DIR" "$CONTAINER" \
          timeout -k 5s 75s \
          /usr/local/bin/qemu-x86_64-static \
          -L /opt/x86_64-sysroot \
          -E LD_LIBRARY_PATH=/opt/x86_64-sysroot/usr/local/lib \
          /opt/x86_64-sysroot/usr/local/bin/python3 \
          -c '
import sys, json, io, runpy
identity = sys.stdin.readline().rstrip("\r\n")
host = sys.stdin.readline().rstrip("\r\n")
passphrase = sys.stdin.readline().rstrip("\r\n")
if not identity or not host or not passphrase:
    sys.exit("Invalid local wrapper settings")
sys.stdin = io.StringIO(json.dumps({
    "identity": identity,
    "host": host,
    "passphrase": passphrase
}) + "\n")
sys.argv = ["/opt/nabto/probe_remote_batch.py", "--settings-stdin"]
runpy.run_path("/opt/nabto/probe_remote_batch.py", run_name="__main__")
'
    echo "Batch $TEST process exit: 0"
    if [ "$TEST" -eq 1 ]; then
        echo "Waiting 15 seconds before second independent session..."
        sleep 15
    fi
    TEST=$((TEST + 1))
    echo
done

PASSPHRASE=""
echo "===== TWO HAOS REMOTE BATCHES COMPLETED ====="
