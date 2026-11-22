#!/usr/bin/env bash
# Export only deployed DEV4 Python sources to Steam Deck for source comparison.
# No /data files, config options, profiles, tokens, certificates or log files.
set -euo pipefail
umask 077

TARGET="${1:-$HOME/Downloads/genvex-dev4-runtime-sources.tar.gz}"
mkdir -p -- "$(dirname -- "$TARGET")"
TMP=$(mktemp "${TARGET}.partial.XXXXXX")
LOG=$(mktemp)
cleanup() { rm -f -- "$TMP" "$LOG"; }
trap cleanup EXIT

if ! ssh -T -p 22222 root@rabbyshome.duckdns.org \
  'docker exec -i app_local_genvex_nabto_remote python3 -' \
  > "$TMP" 2>"$LOG" <<'PY'
import io
from pathlib import Path
import stat
import sys
import tarfile

root = Path("/opt/genvex-remote/runtime")
allowed = (
    "app_bootstrap.py",
    "polling_runtime.py",
    "polling_service.py",
    "snapshot_state.py",
    "persistent_sdk_adapter.py",
    "persistent_rpc45_worker.py",
    "sdk_snapshot_adapter.py",
    "polling_http_server.py",
    "snapshot_contract.py",
    "ipc_auth.py",
)
data = io.BytesIO()
with tarfile.open(fileobj=data, mode="w:gz") as archive:
    for name in allowed:
        path = root / name
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or not 1 <= info.st_size <= 150_000):
            raise SystemExit("SOURCE_EXPORT_BLOCKED")
        blob = path.read_bytes()
        record = tarfile.TarInfo(name)
        record.size = len(blob)
        record.mtime = 0
        record.mode = 0o600
        archive.addfile(record, io.BytesIO(blob))
sys.stdout.buffer.write(data.getvalue())
PY
then
  printf '\033[3J\033[2J\033[H'
  echo "DEV4_SOURCE_EXPORT: FAILED"
  sed -n '1,12p' "$LOG"
  exit 1
fi

if ! tar -tzf "$TMP" > "$LOG"; then
  printf '\033[3J\033[2J\033[H'
  echo "DEV4_SOURCE_EXPORT: INVALID_ARCHIVE"
  exit 1
fi
if [ "$(wc -l < "$LOG")" -ne 10 ]; then
  printf '\033[3J\033[2J\033[H'
  echo "DEV4_SOURCE_EXPORT: UNEXPECTED_FILE_COUNT"
  exit 1
fi
mv -f -- "$TMP" "$TARGET"
printf '\033[3J\033[2J\033[H'
echo "===== DEV4 SOURCE EXPORT ====="
echo "RESULT: PASS"
echo "FILE: $TARGET"
echo "FILES: 10 Python source files"
echo "SHA256: $(sha256sum "$TARGET" | awk '{print $1}')"
echo "===== COMPLETE ====="
