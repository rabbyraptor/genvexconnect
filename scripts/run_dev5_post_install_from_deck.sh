#!/usr/bin/env bash
# DEV5 post-install verification: no App start, stop, update, SDK or profile access.
set -euo pipefail
umask 077
if [[ $# -ne 1 || ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Usage: run_dev5_post_install_from_deck.sh <40-char-tested-commit>" >&2
  exit 2
fi
COMMIT="$1"
WORK=$(mktemp -d /tmp/genvex-dev5-verify.XXXXXX)
trap 'rm -rf -- "$WORK"' EXIT

run() {
  echo "===== DEV5 POST-INSTALL VERIFY ====="
  echo "SOURCE_COMMIT: $COMMIT"
  curl --fail --silent --show-error --location --max-time 60 \
    "https://raw.githubusercontent.com/rabbyraptor/genvexconnect/$COMMIT/scripts/dev5_post_install_verify.py" \
    -o "$WORK/dev5_post_install_verify.py"
  python3 - <<'PY' "$WORK/dev5_post_install_verify.py"
import ast
from pathlib import Path
import sys
ast.parse(Path(sys.argv[1]).read_text())
print("SOURCE_SYNTAX: PASS")
PY
  ssh -T -p 22222 -o BatchMode=yes -o ServerAliveInterval=30 \
    root@rabbyshome.duckdns.org "python3 - --execute-readonly" \
    < "$WORK/dev5_post_install_verify.py"
}

if run > "$WORK/output" 2>&1; then
  CODE=0
else
  CODE=$?
fi
printf '\033[3J\033[2J\033[H'
cat "$WORK/output"
echo "STEAM_DECK_EXIT_CODE: $CODE"
exit "$CODE"
