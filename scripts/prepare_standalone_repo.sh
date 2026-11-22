#!/usr/bin/env bash
# Extract the DEV8 remote-only Git history. Does not access HAOS.
set -euo pipefail

SOURCE="https://github.com/rabbyraptor/genvexconnect.git"
SOURCE_COMMIT="eb4e361f0d0dae351d8b825207d0a9e202cab653"
DESTINATION="https://github.com/rabbyraptor/genvex-remote.git"

die() { printf 'MIGRATION_ERROR: %s\n' "$*" >&2; exit 1; }
[[ $# -eq 2 ]] || die "Usage: $0 --prepare|--verify|--publish /absolute/local/path"
MODE="$1"
DIR="$2"
[[ "$DIR" = /* && "$DIR" != "/" ]] || die "Use an absolute local path"
command -v git >/dev/null || die "git is required"

verify() {
  local path bad
  [[ -d "$DIR/.git" ]] || die "Not a local Git working repository"
  [[ "$(git -C "$DIR" branch --show-current)" == main ]] || die "Expected main branch"
  for path in \
    README.md LICENSE repository.yaml \
    genvex-nabto-remote/config.yaml \
    genvex-nabto-remote/runtime/persistent_rpc45_worker.py \
    genvex-nabto-remote/runtime/raw_registers_v3.py \
    experimental/genvex_remote/sensor_model.py \
    experimental/home_assistant/custom_components/genvex_remote/manifest.json \
    scripts/package_dev8_combined.py \
    scripts/run_dev8_combined_from_deck.sh \
    .github/workflows/remote-nabto-offline.yml; do
    [[ -f "$DIR/$path" ]] || die "Missing source: $path"
  done
  grep -q '^version: "0.1.0-dev8"$' "$DIR/genvex-nabto-remote/config.yaml" ||
    die "Unexpected App version"
  grep -q '"version": "0.2.0"' \
    "$DIR/experimental/home_assistant/custom_components/genvex_remote/manifest.json" ||
    die "Unexpected Home Assistant version"
  bad="$(git -C "$DIR" ls-files | grep -E \
    '^(custom_components/genvex_connect/|hacs\.json$|\.github/workflows/(hacs|hassfest|formatting)\.)' || true)"
  [[ -z "$bad" ]] || die "Inherited LAN integration or HACS files present"
  bad="$(git -C "$DIR" ls-files | grep -Ei \
    '\.(so|dll|dylib|pem|p12|pfx|key|crt|db|sqlite|pcap)$' || true)"
  [[ -z "$bad" ]] || die "Credential-like or proprietary binary file present"
  [[ -z "$(git -C "$DIR" status --porcelain)" ]] || die "Working tree not clean"
  printf 'STANDALONE_VERIFY: PASS\n'
  printf 'APP_VERSION: 0.1.0-dev8\nHA_VERSION: 0.2.0\n'
  printf 'HISTORY_COMMITS: %s\n' "$(git -C "$DIR" rev-list --count HEAD)"
  printf 'TRACKED_FILES: %s\n' "$(git -C "$DIR" ls-files | wc -l | tr -d ' ')"
  printf 'STANDALONE_HEAD: %s\n' "$(git -C "$DIR" rev-parse HEAD)"
}

case "$MODE" in
  --prepare)
    git filter-repo --version >/dev/null 2>&1 ||
      die "git-filter-repo required; install it before retrying"
    [[ ! -e "$DIR" ]] || die "Destination exists; select a new path"
    mkdir -p "$(dirname "$DIR")"
    TMP="$(mktemp -d "$(dirname "$DIR")/.genvex-remote-extract.XXXXXXXX")"
    trap 'rm -rf -- "$TMP"' EXIT

    git clone --quiet --no-tags --single-branch --branch dev8-staging \
      "$SOURCE" "$TMP/repo"
    REPO="$TMP/repo"
    git -C "$REPO" cat-file -e "$SOURCE_COMMIT^{commit}" ||
      die "Pinned commit missing"
    git -C "$REPO" show "$SOURCE_COMMIT:LICENSE" > "$TMP/LICENSE"
    git -C "$REPO" checkout --quiet --detach "$SOURCE_COMMIT"
    git -C "$REPO" switch --quiet -c main
    git -C "$REPO" branch -q -D dev8-staging
    git -C "$REPO" remote remove origin

    # Preserve all relevant historical commits; exclude original LAN/HACS code.
    git -C "$REPO" filter-repo --force --prune-empty always \
      --path experimental/genvex_remote/ \
      --path experimental/home_assistant/ \
      --path genvex-nabto-remote/ \
      --path haos-apps/ \
      --path docs/ \
      --path scripts/ \
      --path tests/ \
      --path tools/haos_dev_mcp/ \
      --path .github/workflows/remote-app-image-build.yml \
      --path .github/workflows/remote-app-offline.yml \
      --path .github/workflows/remote-dev-mcp-offline.yml \
      --path .github/workflows/remote-nabto-offline.yml >/dev/null

    cp "$TMP/LICENSE" "$REPO/LICENSE"
    cat > "$REPO/README.md" <<'STANDALONE_README'
# Genvex Remote

Standalone experimental **remote, read-only** Home Assistant integration for
Genvex Connect/Nilan gateways using proprietary legacy Nabto Micro.

## Live DEV8 verification — 22 November 2026

On a Genvex Optima 270 with Home Assistant OS ARM64:

- HAOS App version **0.1.0-dev8**, persistent legacy x86-64 SDK via QEMU.
- Separate Home Assistant integration **genvex_remote 0.2.0**.
- **23/23 available entities:** five scaled readings, 17 raw RPC45
  diagnostic registers, and a data-age sensor.
- A subsequent live polling cycle finished in **0.07 seconds** with the
  worker/session reused and two serial RPC45 reads.
- There are no remote write/control features. Longer live stability and
  controlled failure/reauthentication checks remain pending.

## Architecture

Genvex gateway → encrypted Nabto Micro → legacy SDK x86-64 through QEMU
→ persistent native ARM64 App worker → authenticated private v1/v3 snapshots
→ Home Assistant coordinator → 23 sensors.

The iPhone/Android app is not used for communications. Our code controls
RPC45 requests, polling, snapshots, validation and entity exposure; the
proprietary SDK provides the transport/session.

## Source layout

The first standalone migration intentionally **preserves the DEV8 paths**
so its existing tests and installation scripts remain intact:

- genvex-nabto-remote/: Home Assistant OS development App.
- experimental/genvex_remote/: shared backend and offline tests.
- experimental/home_assistant/: Home Assistant integration and tests.
- scripts/: builders, operator gates and historical scripts.
- docs/: protocol research, test evidence and releases.
- tools/haos_dev_mcp/: read-only development MCP code.

See [live test evidence](docs/dev8-live-verification-2026-11-22.md),
[release gate](docs/dev8-4-combined-release-gate.md) and
[documentation index](docs/README.md).

## Developer checks

Run from the repository root:

    python3 scripts/check_remote_runtime_parity.py --check
    python3 -m unittest discover -s experimental/genvex_remote -p 'test_*.py'
    python3 -m unittest discover -s experimental/home_assistant/tests -p 'test_*.py'
    python3 -m unittest discover -s genvex-nabto-remote/tests -p 'test_*.py'
    python3 scripts/package_dev8_combined.py

## Origin and license

History was extracted from the remote development in
[rabbyraptor/genvexconnect](https://github.com/rabbyraptor/genvexconnect),
a fork of [superrob/genvexconnect](https://github.com/superrob/genvexconnect).

The original LAN/HACS integration is **not included** in this repository.
Source code is [GPL-3.0](LICENSE); the proprietary Nabto SDK is a separate
dependency with unresolved public redistribution rights.
STANDALONE_README

    cat > "$REPO/.gitignore" <<'STANDALONE_IGNORE'
__pycache__/
*.py[cod]
.pytest_cache/
dist/
.venv/
*.egg-info/
client.crt
client-encrypted.key
options.json
ipc-token
STANDALONE_IGNORE

    cat > "$REPO/repository.yaml" <<'STANDALONE_CONFIG'
name: "Genvex Remote development"
url: "https://github.com/rabbyraptor/genvex-remote"
maintainer: "Genvex Remote development"
STANDALONE_CONFIG

    # Switch push-trigger filters from the former staging branch to new main.
    for workflow in "$REPO"/.github/workflows/remote-*.yml; do
      [[ -f "$workflow" ]] || continue
      sed -i 's/^      - remote-nabto-connection$/      - main/' "$workflow"
    done

    git -C "$REPO" add README.md LICENSE repository.yaml .gitignore .github/workflows
    git -C "$REPO" commit --quiet -m \
      "chore: establish independent Genvex Remote repository from filtered history" ||
      die "Configure Git user.name and user.email, then retry"
    DIR="$REPO"
    verify
    DIR="$2"
    mv "$REPO" "$DIR"
    trap - EXIT
    rm -rf -- "$TMP"
    printf 'MIGRATION_PREPARE: PASS\n'
    printf 'LOCAL_REPOSITORY: %s\n' "$DIR"
    printf 'NEXT: Create EMPTY PRIVATE rabbyraptor/genvex-remote, then run --publish\n'
    ;;
  --verify)
    verify
    ;;
  --publish)
    verify
    [[ -z "$(git -C "$DIR" remote)" ]] ||
      die "Unexpected remote already configured; inspect before publication"
    REFS="$(git ls-remote "$DESTINATION")" ||
      die "Create an empty GitHub repository and configure Git authentication first"
    [[ -z "$REFS" ]] ||
      die "Destination GitHub repository is not empty; refusing push"
    git -C "$DIR" remote add origin "$DESTINATION"
    if ! git -C "$DIR" push -u origin main; then
      git -C "$DIR" remote remove origin
      die "Publish failed; verify GitHub credentials and repo permissions"
    fi
    printf 'MIGRATION_PUBLISH: PASS\n'
    printf 'REMOTE_URL: %s\n' "$DESTINATION"
    ;;
  *)
    die "Mode must be --prepare, --verify or --publish"
    ;;
esac
