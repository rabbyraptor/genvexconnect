#!/bin/sh
# Build only a NEW, separate image; never touch the installed Genvex App,
# Home Assistant Core, existing Nabto credentials or any profile files.
set -eu
umask 077

PIN=7d2fb0f51038f246d6e290e00b11f4940996ca72
TAG="genvex-nabto-remote:dev-$(printf '%.12s' "$PIN")"
WORK=$(mktemp -d /tmp/genvex-remote-build.XXXXXX)
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

echo "===== GENVEX REMOTE SEPARATE HAOS APP IMAGE BUILD v1 ====="
echo "Source commit: $PIN"
echo "This downloads public build dependencies and may use several GB of disk."
echo "No real profile, Nabto identity, passphrase, or IPC token is read."
echo "No installed App, container, or Home Assistant integration is changed."

test "$(uname -m)" = aarch64 || {
  echo "FAIL: This build is intended for the HAOS ARM64 host." >&2
  exit 2
}
command -v docker >/dev/null
command -v curl >/dev/null
command -v tar >/dev/null
test -d /mnt/data

# Stop early on very low free disk; Docker build needs space for foreign
# architecture sysroots and SDK extraction. Do not prune existing images.
AVAILABLE_KB=$(df -Pk /mnt/data | awk 'NR==2 {print $4}')
case "$AVAILABLE_KB" in
  ''|*[!0-9]*) echo "FAIL: Cannot determine available storage." >&2; exit 2 ;;
esac
if [ "$AVAILABLE_KB" -lt 3145728 ]; then
  echo "FAIL: Less than 3 GiB available on HAOS data partition; build not started." >&2
  exit 2
fi

curl -fsSL --retry 3 --max-time 120 \
  "https://codeload.github.com/rabbyraptor/genvexconnect/tar.gz/$PIN" \
  -o "$WORK/source.tar.gz"
tar -xzf "$WORK/source.tar.gz" -C "$WORK"
SOURCE=$(find "$WORK" -type d -name genvex-nabto-remote -print -quit)
test -n "$SOURCE"
test -f "$SOURCE/Dockerfile"
test -f "$SOURCE/runtime/app_bootstrap.py"
test -f "$SOURCE/config.yaml"

echo "Building NEW image (SDK, QEMU, ARM64 runtime and compile smoke test)..."
DOCKER_BUILDKIT=1 docker build \
  --platform linux/arm64 \
  --build-arg BUILD_ARCH=aarch64 \
  --build-arg BUILD_VERSION=0.1.0-dev1 \
  --tag "$TAG" \
  "$SOURCE"

echo "Checking built image architecture and isolated read-only imports..."
test "$(docker image inspect "$TAG" --format '{{.Architecture}}')" = arm64
test "$(docker image inspect "$TAG" --format '{{.Config.Labels.io.hass.type}}')" = app
test "$(docker image inspect "$TAG" --format '{{.Config.ExposedPorts}}')" = '<no value>' || {
  # Some Docker versions render absent exposed ports as <nil>.
  PORTS=$(docker image inspect "$TAG" --format '{{json .Config.ExposedPorts}}')
  test "$PORTS" = null || test "$PORTS" = '{}'
}

docker run --rm --network none --read-only --tmpfs /tmp \
  --entrypoint python3 "$TAG" \
  -c 'import sys; sys.path.insert(0, "/opt/genvex-remote/runtime"); import app_bootstrap, polling_runtime, sdk_snapshot_adapter, polling_http_server; print("PASS: native ARM64 App runtime imports")'

echo "===== PASS: ISOLATED GENVEX REMOTE APP IMAGE BUILD ====="
echo "New image tag: $TAG"
echo "This is NOT an installed or started HAOS App."
echo "No certificate or real gateway was accessed."
