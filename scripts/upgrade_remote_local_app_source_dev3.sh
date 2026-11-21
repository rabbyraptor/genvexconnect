#!/usr/bin/env bash
# Operator-approved source-only dev2 -> dev3 transaction for HAOS.
# Does not reload Supervisor, build/update/start the App or touch apps/data.
set -euo pipefail
umask 077

usage() {
  echo "Usage: bash $0 --preflight|--apply ARCHIVE SHA256SUMS" >&2
  exit 2
}
[ "$#" -eq 3 ] || usage
MODE=$1
ARCHIVE=$2
SUMS=$3
case "$MODE" in --preflight|--apply) ;; *) usage ;; esac
[ -f "$ARCHIVE" ] && [ ! -L "$ARCHIVE" ] || usage
[ -f "$SUMS" ] && [ ! -L "$SUMS" ] || usage
ARCHIVE=$(realpath -- "$ARCHIVE")
SUMS=$(realpath -- "$SUMS")
[ "$(basename -- "$ARCHIVE")" = "genvex-nabto-remote-local-app-source.tar.gz" ] || usage
[ "$(basename -- "$SUMS")" = "APP_SOURCE_SHA256SUMS" ] || usage
[ "$(dirname -- "$ARCHIVE")" = "$(dirname -- "$SUMS")" ] || usage
(
  cd "$(dirname -- "$ARCHIVE")"
  sha256sum -c --status -- APP_SOURCE_SHA256SUMS
) || { echo "BLOCKED: local archive checksum mismatch"; exit 1; }
DIGEST=$(sha256sum "$ARCHIVE")
DIGEST=${DIGEST%% *}

# Validate archive BEFORE any SSH operation, including hidden entries,
# links, path traversal, duplicate members and the exact dev3 manifest.
python3 - "$ARCHIVE" <<'PY'
from pathlib import PurePosixPath
import sys
import tarfile

required = {"config.yaml", "Dockerfile", "run.sh",
            "runtime/app_bootstrap.py", "runtime/profile_provision.py"}
with tarfile.open(sys.argv[1], "r:gz") as archive:
    members = archive.getmembers()
    names = set()
    for item in members:
        path = PurePosixPath(item.name)
        parts = path.parts
        if (not item.isfile()
                or not (len(parts) == 2 and parts[0] == "genvex_nabto_remote"
                        and parts[1] in ("Dockerfile", "config.yaml", "run.sh")
                        or len(parts) == 3
                        and parts[:2] == ("genvex_nabto_remote", "runtime")
                        and parts[2].endswith(".py")
                        and not parts[2].startswith("."))
                or ".." in parts or item.size > 1000000
                or len(item.name) > 160 or item.name in names):
            raise SystemExit("BLOCKED: unsafe App source archive")
        names.add(item.name)
    if not {"genvex_nabto_remote/" + n for n in required}.issubset(names):
        raise SystemExit("BLOCKED: missing required App source")
    config = archive.extractfile("genvex_nabto_remote/config.yaml").read()
    for entry in (b'version: "0.1.0-dev3"', b"boot: manual_only",
                  b"host_network: false", b"stage: experimental",
                  b"slug: \"genvex_nabto_remote\""):
        if entry not in config.splitlines():
            raise SystemExit("BLOCKED: unsafe dev3 manifest")
print("PASS: dev3 source archive allowlisted and SHA256 verified")
PY

SSH_HOST="root@rabbyshome.duckdns.org"
SSH_PORT=22222
# Respect the operator's existing SSH identity/configuration.
SSH=(ssh -T -p "$SSH_PORT" -o BatchMode=yes "$SSH_HOST")

# First run the separate read-only host gate, using its exact branch version.
GATE="$(dirname -- "$ARCHIVE")/audit_haos_dev3_source_transaction_preflight_v1.sh"
if [ ! -f "$GATE" ]; then
  echo "BLOCKED: reviewed source transaction gate required beside archive"
  exit 1
fi
echo "===== DEV3 SOURCE TRANSACTION: HOST READ-ONLY GATE ====="
"${SSH[@]}" 'sh -s -- --execute-readonly' < "$GATE" || exit 1
if [ "$MODE" = --preflight ]; then
  echo "PASS: preflight complete; no HAOS files changed"
  exit 0
fi

# The second SSH session independently rechecks the essential stop/baseline
# gates before mutation, to reject changes since the read-only session.
# This command never reads options, PEMs or App-private data.
echo "===== DEV3 SOURCE-ONLY BACKUP / SWAP ====="
"${SSH[@]}" "sh -c '
  set -eu
  umask 077
  BASE=/mnt/data/supervisor/apps/local
  SRC=\$BASE/genvex_nabto_remote
  STAGE=\$BASE/.genvex-remote-dev3-source-stage
  BACKUP=\$BASE/.genvex-remote-dev2-source-backup
  EXPECTED=$DIGEST
  [ -d \$SRC ] && [ ! -L \$SRC ] || { echo BLOCKED-source; exit 1; }
  [ ! -e \$STAGE ] && [ ! -L \$STAGE ] || { echo BLOCKED-stage; exit 1; }
  [ ! -e \$BACKUP ] && [ ! -L \$BACKUP ] || { echo BLOCKED-backup; exit 1; }
  META=\$(ha apps info local_genvex_nabto_remote </dev/null 2>/dev/null |
    sed -n \"/^state: /p; /^boot: /p; /^version: /p\")
  printf \"%s\\n\" \"\$META\" | grep -qx \"state: stopped\" || exit 1
  printf \"%s\\n\" \"\$META\" | grep -qx \"boot: manual\" || exit 1
  printf \"%s\\n\" \"\$META\" | grep -qx \"version: 0.1.0-dev2\" || exit 1
  if docker inspect --type container app_local_genvex_nabto_remote >/dev/null 2>&1; then
    [ \"\$(docker inspect --type container app_local_genvex_nabto_remote --format \"{{.State.Running}}\")\" = false ] || exit 1
  fi
  [ \"\$(sha256sum \$SRC/config.yaml | cut -d \" \" -f 1)\" = 9c3099526543b19d6227cc8e56fbdc63b02c1c1635deff5a08f7afb7f0b1abb4 ] || exit 1
  [ \"\$(sha256sum \$SRC/Dockerfile | cut -d \" \" -f 1)\" = 5c7edfb109ccad4b09a19ff28c3173e405bcb33eb26034174ee10de83d2f4cdd ] || exit 1
  [ \"\$(sha256sum \$SRC/run.sh | cut -d \" \" -f 1)\" = 50c68a9defb3c47621ab6d3b901b3e645ac19f539616457f469a1cb76a91f398 ] || exit 1
  [ \"\$(sha256sum \$SRC/runtime/app_bootstrap.py | cut -d \" \" -f 1)\" = 9e8862450d6204d21136baae25ce37aa24aa591f1008842c5914911517db7db1 ] || exit 1
  [ \"\$(sha256sum \$SRC/runtime/profile_provision.py | cut -d \" \" -f 1)\" = f5b4580faeacedd1d2f73f1392864198b457af230d723217f49afa68949b67a6 ] || exit 1
  mkdir -m 0700 \$STAGE
  swapped=0
  cleanup() {
    if [ \$swapped -eq 1 ] && [ ! -e \$SRC ] && [ -d \$BACKUP ]; then
      mv \$BACKUP \$SRC || echo CRITICAL-ROLLBACK-FAILED
    fi
    if [ -d \$STAGE ]; then rm -rf -- \$STAGE; fi
  }
  trap cleanup EXIT HUP INT TERM
  cat > \$STAGE/archive.tar.gz
  printf \"%s  %s\\n\" \$EXPECTED \$STAGE/archive.tar.gz | sha256sum -c >/dev/null || {
    echo BLOCKED-archive-checksum; exit 1;
  }
  tar -xzf \$STAGE/archive.tar.gz -C \$STAGE
  rm \$STAGE/archive.tar.gz
  [ -f \$STAGE/genvex_nabto_remote/config.yaml ] || exit 1
  grep -qx \"version: \\\"0.1.0-dev3\\\"\" \$STAGE/genvex_nabto_remote/config.yaml || exit 1
  [ -f \$STAGE/genvex_nabto_remote/runtime/profile_provision.py ] || exit 1
  # Recheck source baseline immediately before the swap.
  [ \"\$(sha256sum \$SRC/config.yaml | cut -d \" \" -f 1)\" = 9c3099526543b19d6227cc8e56fbdc63b02c1c1635deff5a08f7afb7f0b1abb4 ] || exit 1
  [ \"\$(sha256sum \$SRC/Dockerfile | cut -d \" \" -f 1)\" = 5c7edfb109ccad4b09a19ff28c3173e405bcb33eb26034174ee10de83d2f4cdd ] || exit 1
  [ \"\$(sha256sum \$SRC/run.sh | cut -d \" \" -f 1)\" = 50c68a9defb3c47621ab6d3b901b3e645ac19f539616457f469a1cb76a91f398 ] || exit 1
  [ \"\$(sha256sum \$SRC/runtime/app_bootstrap.py | cut -d \" \" -f 1)\" = 9e8862450d6204d21136baae25ce37aa24aa591f1008842c5914911517db7db1 ] || exit 1
  [ \"\$(sha256sum \$SRC/runtime/profile_provision.py | cut -d \" \" -f 1)\" = f5b4580faeacedd1d2f73f1392864198b457af230d723217f49afa68949b67a6 ] || exit 1
  mv \$SRC \$BACKUP
  swapped=1
  mv \$STAGE/genvex_nabto_remote \$SRC || exit 1
  swapped=0
  rmdir \$STAGE
  trap - EXIT HUP INT TERM
  echo PASS-source-swap-dev3-backup-retained
'" < "$ARCHIVE"
echo "PASS: dev3 App SOURCE swapped, dev2 source backup retained"
echo "IMPORTANT: Supervisor was NOT reloaded or updated; installed App remains dev2."
