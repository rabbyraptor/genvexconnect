#!/usr/bin/env bash
# PREPARED ONLY. Never run on HAOS without explicit operator authorization.
# Stages source under a NEW local Supervisor App folder. Does not install,
# build, start, reload the store or modify an existing App.
set -euo pipefail

usage() {
  echo "Usage: bash $0 --preflight|--stage ARCHIVE SHA256SUMS" >&2
  echo "Only --stage modifies the new App source folder on HAOS." >&2
  exit 2
}

test "$#" = 3 || usage
MODE=$1
ARCHIVE=$2
SUMS=$3
case "$MODE" in --preflight|--stage) ;; *) usage ;; esac

# These are the previously audited HAOS SSH endpoint and local App root.
SSH_HOST="root@rabbyshome.duckdns.org"
SSH_PORT=22222
SSH_KEY="${HOME}/.ssh/id_ed25519"
BASE="/mnt/data/supervisor/apps/local"
DEST="$BASE/genvex_nabto_remote"

test -f "$ARCHIVE" && test -f "$SUMS" && test -r "$ARCHIVE" && test -r "$SUMS"
test -f "$SSH_KEY"
ARCHIVE=$(realpath -- "$ARCHIVE")
SUMS=$(realpath -- "$SUMS")
DIR=$(dirname -- "$ARCHIVE")
test "$(basename -- "$ARCHIVE")" = "genvex-nabto-remote-local-app-source.tar.gz"

(
  cd "$DIR"
  sha256sum --check --status -- "$SUMS"
)

# Reject path traversal, links, special files, unexpected archive members,
# duplicate files and credential-like paths BEFORE streaming anything.
python3 - "$ARCHIVE" <<'PY'
import pathlib
import sys
import tarfile

archive = pathlib.Path(sys.argv[1])
required = {
    "genvex_nabto_remote/config.yaml",
    "genvex_nabto_remote/Dockerfile",
    "genvex_nabto_remote/run.sh",
    "genvex_nabto_remote/runtime/app_bootstrap.py",
    "genvex_nabto_remote/runtime/diagnostic_http_server.py",
}
with tarfile.open(archive, "r:gz") as stream:
    members = stream.getmembers()
    names = [m.name for m in members]
    if len(members) < len(required) or len(names) != len(set(names)):
        raise SystemExit("Invalid or duplicate source files")
    if not required.issubset(names):
        raise SystemExit("Missing required App source")
    for member in members:
        parts = pathlib.PurePosixPath(member.name).parts
        if not member.isfile() or not (
            len(parts) == 2 and parts[0] == "genvex_nabto_remote"
            and parts[1] in ("Dockerfile", "config.yaml", "run.sh")
            or len(parts) == 3 and parts[:2] == ("genvex_nabto_remote", "runtime")
            and parts[2].endswith(".py") and not parts[2].startswith(".")
        ):
            raise SystemExit("Unexpected member in App source archive")
        if member.size > 1000000 or len(member.name) > 160:
            raise SystemExit("Oversize source member")
    config = stream.extractfile("genvex_nabto_remote/config.yaml").read()
    for line in (
        b"diagnostic_only: false", b"boot: manual_only",
        b"host_network: false", b"stage: experimental",
    ):
        if line not in config:
            raise SystemExit("Missing App source safety setting")
print("PASS: source archive safely allowlisted and checksum verified")
PY

SSH=(ssh -i "$SSH_KEY" -p "$SSH_PORT" -o BatchMode=yes)

echo "===== READ-ONLY REMOTE PRE-STAGING CHECK ====="
"${SSH[@]}" "$SSH_HOST" "sh -c 'set -eu; test -d $BASE; test ! -e $DEST; test ! -L $DEST; test ! -e $BASE/.genvex-nabto-remote-stage'"

if [ "$MODE" = "--preflight" ]; then
  echo "PASS: preflight only; no remote files changed"
  exit 0
fi

# After explicit user approval, stream only the verified tar archive.
# A hidden temporary directory prevents the Supervisor from discovering
# an incomplete App. Atomic move makes the finished source visible.
echo "===== STAGING NEW EXPERIMENTAL APP SOURCE (NO INSTALL/START) ====="
"${SSH[@]}" "$SSH_HOST" 'sh -c '"'"'
  set -eu
  umask 077
  BASE=/mnt/data/supervisor/apps/local
  DEST="$BASE/genvex_nabto_remote"
  STAGE="$BASE/.genvex-nabto-remote-stage"
  test -d "$BASE"
  test ! -e "$DEST" && test ! -L "$DEST"
  test ! -e "$STAGE" && test ! -L "$STAGE"
  mkdir -m 0700 "$STAGE"
  trap '"'"'rm -rf "$STAGE"'"'"' EXIT
  tar -xz -C "$STAGE"
  test -f "$STAGE/genvex_nabto_remote/config.yaml"
  test -f "$STAGE/genvex_nabto_remote/Dockerfile"
  test -f "$STAGE/genvex_nabto_remote/run.sh"
  test ! -e "$DEST" && test ! -L "$DEST"
  mv "$STAGE/genvex_nabto_remote" "$DEST"
  rmdir "$STAGE"
  trap - EXIT
  echo "PASS: separate experimental App source staged; Supervisor not reloaded"
'"'"'' < "$ARCHIVE"
echo "PASS: no existing App was overwritten; no App installed or started"
