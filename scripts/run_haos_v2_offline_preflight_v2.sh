#!/bin/sh
# V2 source-only HAOS ARM64 preflight with the original repository layout.
# No Nabto SDK, credentials, profile reads, RPC, App install or HA Core changes.
set -eu
umask 077

# The archive includes both source and all its cross-directory test fixtures.
PINNED_SHA="189d48a641ef613023c1060f7d6cf2b2f7369b34"
APP="app_local_genvex_nabto_runtime_test"

usage() {
  printf '%s\n' "Usage: $0 --preflight | --execute-offline" >&2
  exit 2
}

[ "$#" -eq 1 ] || usage
case "$1" in
  --preflight)
    printf '%s\n' "===== GENVEX V2 HAOS OFFLINE PREFLIGHT v2 / REPO LAYOUT ====="
    printf '%s\n' "Pinned source: $PINNED_SHA"
    printf '%s\n' "Stage original experimental/genvex_remote, experimental/home_assistant and scripts paths."
    printf '%s\n' "Run full offline backend, HA scaffold and syntax tests in isolated test App."
    printf '%s\n' "No SDK, credentials, device RPC, App install or Home Assistant Core changes."
    printf '%s\n' "PASS: v2 preview complete; no container/network operations."
    exit 0
    ;;
  --execute-offline) ;;
  *) usage ;;
esac

WORK=""
STAGE=""
cleanup() {
  if [ -n "$STAGE" ]; then
    docker exec "$APP" rm -rf "$STAGE" >/dev/null 2>&1 || true
  fi
  if [ -n "$WORK" ]; then
    rm -rf "$WORK"
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

printf '%s\n' "===== GENVEX V2 HAOS ARM64 OFFLINE REPO-LAYOUT TEST v2 ====="
printf '%s\n' "Pinned source: $PINNED_SHA"
test "$(docker inspect "$APP" --format '{{.State.Status}}')" = running
WORK=$(mktemp -d /tmp/genvex-haos-v2-offline.XXXXXX)
curl -fsSL --max-time 60 \
  "https://codeload.github.com/rabbyraptor/genvexconnect/tar.gz/$PINNED_SHA" \
  -o "$WORK/source.tar.gz"
tar -xzf "$WORK/source.tar.gz" -C "$WORK"
SRC=$(find "$WORK" -type d -path '*/experimental/genvex_remote' -print -quit)
test -n "$SRC"
PROJECT_ROOT=$(dirname "$(dirname "$SRC")")
test -f "$SRC/test_v2_polling_state.py"
test -f "$SRC/test_v2_snapshot_bridge.py"
test -f "$SRC/v2_snapshot_bridge.py"
test -f "$PROJECT_ROOT/scripts/run_optima270_one_read_from_deck.sh"
test -f "$PROJECT_ROOT/scripts/probe_optima270_seven_snapshot_v2.py"
test -f "$PROJECT_ROOT/scripts/probe_optima270_single_source_candidate.py"
test -f "$PROJECT_ROOT/scripts/probe_optima270_all_source_candidates_batch.py"
test -f "$PROJECT_ROOT/experimental/home_assistant/tests/test_runtime_client_v2_draft.py"
test -f "$PROJECT_ROOT/experimental/home_assistant/custom_components/genvex_remote/snapshot_v2_draft.py"

STAGE=$(docker exec "$APP" mktemp -d /tmp/genvex-v2-test.XXXXXX)
docker exec "$APP" mkdir -p "$STAGE/project"
# Staging under project/ preserves Path(__file__).parents[2] references in
# script-dependent offline unit tests; the former v1 runner omitted scripts/.
tar -C "$PROJECT_ROOT" -cf - \
  experimental/genvex_remote experimental/home_assistant scripts \
  | docker exec -i "$APP" tar -xf - -C "$STAGE/project"
docker exec "$APP" test -f "$STAGE/project/scripts/run_optima270_one_read_from_deck.sh"
docker exec "$APP" test -f "$STAGE/project/scripts/probe_optima270_seven_snapshot_v2.py"
docker exec "$APP" test -f "$STAGE/project/experimental/home_assistant/tests/test_snapshot_v2_draft.py"

printf '%s\n' "Running all backend tests in intact repository layout..."
docker exec "$APP" sh -c 'cd "$1/project/experimental/genvex_remote" && python3 -m unittest discover -s . -p "test_*.py" -v' sh "$STAGE"
printf '%s\n' "Running isolated Home Assistant snapshot/reader tests..."
docker exec "$APP" sh -c 'cd "$1/project/experimental/home_assistant/tests" && python3 -m unittest discover -s . -p "test_*.py" -v' sh "$STAGE"
printf '%s\n' "Checking source syntax..."
docker exec "$APP" python3 -m compileall -q "$STAGE/project/experimental/genvex_remote" "$STAGE/project/experimental/home_assistant" "$STAGE/project/scripts"
printf '%s\n' "===== PASS: GENVEX V2 HAOS OFFLINE REPO-LAYOUT TEST v2 ====="
printf '%s\n' "No live RPC, credentials, installed App or Core component changed."
