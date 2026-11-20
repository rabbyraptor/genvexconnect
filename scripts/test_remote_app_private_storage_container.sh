#!/bin/sh
# CI-only: checks private PEM staging inside native ARM64 App image.
# Uses fake PEM markers, Docker tmpfs, no network, no HAOS data mounts.
set -eu

IMAGE=${1:-genvex-nabto-remote:ci}
case "$IMAGE" in
  *[!a-zA-Z0-9_./:@-]*|'') echo "Invalid image argument" >&2; exit 2 ;;
esac
echo "===== ARM64 PRIVATE STORAGE CONTAINER SMOKE ====="
docker run --rm --network none --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,mode=1777 \
  --tmpfs /data:rw,nosuid,nodev,mode=0755 \
  --entrypoint python3 "$IMAGE" -c '
import io
import os
from pathlib import Path
import stat
import struct
import sys

sys.path.insert(0, "/opt/genvex-remote/runtime")
from profile_provision import provision
from app_bootstrap import validate_private_profile

root = Path("/data")
assert os.geteuid() == 0, "Unexpected user for CI image"
assert stat.S_IMODE(root.stat().st_mode) == 0o755
assert root.stat().st_uid == os.geteuid()

cert = b"-----BEGIN CERTIFICATE-----\\nFAKE-ONLY\\n-----END CERTIFICATE-----\\n"
key = (b"-----BEGIN ENCRYPTED PRIVATE KEY-----\\nFAKE-ONLY\\n"
       b"-----END ENCRYPTED PRIVATE KEY-----\\n")
blob = struct.pack(">I", len(cert)) + cert + struct.pack(">I", len(key)) + key
provision(io.BytesIO(blob), data_dir=root)
profile = root / "profile"
assert stat.S_IMODE(profile.stat().st_mode) == 0o700
for name in ("client.crt", "client-encrypted.key"):
    assert stat.S_IMODE((profile / name).stat().st_mode) == 0o600
validate_private_profile(profile)
try:
    provision(io.BytesIO(blob), data_dir=root)
except FileExistsError:
    pass
else:
    raise AssertionError("Second import unexpectedly accepted")
assert stat.S_IMODE(root.stat().st_mode) == 0o755
print("PASS: native App image isolated fake-only 0755/0700/0600 profile lifecycle")
'
echo "===== ARM64 STORAGE CONTAINER SMOKE COMPLETE ====="
