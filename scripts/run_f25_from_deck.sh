#!/bin/sh
# Run F2.5 from Steam Deck. Transfer script to a unique temporary HAOS file
# BEFORE executing it. Do not run "ssh ... sh < script": CLI subprocesses
# may read the script's stdin and cause unterminated-quote parsing failures.
set -eu

DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SCRIPT="$DIR/run_f25_mount_attestation.sh"
[ -f "$SCRIPT" ] || { echo "FAIL: missing F2.5 script"; exit 1; }
sh -n "$SCRIPT" || { echo "FAIL: F2.5 script syntax"; exit 1; }

ssh -i "$HOME/.ssh/id_ed25519" \
    -p 22222 -o BatchMode=yes \
    root@rabbyshome.duckdns.org \
    'set -eu; tmp=$(mktemp /tmp/genvex-f25.XXXXXX); trap "rm -f \"$tmp\"" EXIT; cat > "$tmp"; sh "$tmp"' \
    < "$SCRIPT"
