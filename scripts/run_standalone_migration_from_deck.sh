#!/usr/bin/env bash
# Prepare, verify and publish standalone Genvex Remote from Steam Deck.
# Requires an existing EMPTY private GitHub destination and Git credentials.
# Does not touch HAOS or the original fork's branches.
set -euo pipefail
umask 077

if [[ $# -ne 1 || ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Usage: run_standalone_migration_from_deck.sh <pinned-migration-source-SHA>" >&2
  exit 2
fi
PIN="$1"
DIR="${GENVEX_STANDALONE_DIR:-$HOME/genvex-remote-standalone}"
[[ "$DIR" == /* ]] || { echo "Use an absolute GENVEX_STANDALONE_DIR" >&2; exit 2; }

TEMP="$(mktemp -d /tmp/genvex-repo-migration.XXXXXXXX)"
LOG="$TEMP/log.txt"
RESULT=0

finish() {
  printf '\033[3J\033[2J\033[H'
  echo "===== GENVEX STANDALONE REPOSITORY MIGRATION ====="
  cat "$LOG" 2>/dev/null || true
  echo "STEAM_DECK_EXIT_CODE: $RESULT"
  rm -rf -- "$TEMP"
}
trap finish EXIT

run_migration() {
  echo "SOURCE_COMMIT: $PIN"
  echo "TARGET_REPO: rabbyraptor/genvex-remote"
  echo "LOCAL_SOURCE: $DIR"
  command -v git >/dev/null || { echo "GIT_REQUIRED"; return 2; }
  command -v python3 >/dev/null || { echo "PYTHON_REQUIRED"; return 2; }
  command -v curl >/dev/null || { echo "CURL_REQUIRED"; return 2; }

  if ! git filter-repo --version >/dev/null 2>&1; then
    echo "FILTER_REPO_INSTALL: temporary virtual environment"
    python3 -m venv "$TEMP/venv"
    "$TEMP/venv/bin/python" -m pip install --quiet git-filter-repo
    export PATH="$TEMP/venv/bin:$PATH"
    git filter-repo --version >/dev/null
  fi

  curl --fail --silent --show-error --location --retry 3 \
    "https://raw.githubusercontent.com/rabbyraptor/genvexconnect/$PIN/scripts/prepare_standalone_repo.sh" \
    -o "$TEMP/migrate.sh"
  bash -n "$TEMP/migrate.sh"
  if [[ ! -d "$DIR/.git" ]]; then
    [[ ! -e "$DIR" ]] || { echo "LOCAL_DIR_EXISTS_NOT_GIT"; return 2; }
    bash "$TEMP/migrate.sh" --prepare "$DIR" || return $?
  fi

  bash "$TEMP/migrate.sh" --verify "$DIR" || return $?
  if git -C "$DIR" remote get-url origin >/dev/null 2>&1; then
    echo "ORIGIN_ALREADY_SET: check published commit"
    local upstream_sha local_sha
    local_sha="$(git -C "$DIR" rev-parse HEAD)"
    upstream_sha="$(GIT_TERMINAL_PROMPT=0 git -C "$DIR" ls-remote origin refs/heads/main | cut -f1)" || return $?
    [[ -n "$upstream_sha" && "$upstream_sha" == "$local_sha" ]] ||
      { echo "ORIGIN_MAIN_MISMATCH"; return 2; }
    echo "MIGRATION_PUBLISH: ALREADY_MATCHED"
  else
    bash "$TEMP/migrate.sh" --publish "$DIR" || return $?
  fi
  echo "MIGRATION_OPERATOR_GATE: PASS"
}

run_migration >"$LOG" 2>&1 || RESULT=$?
exit "$RESULT"
