#!/usr/bin/env python3
"""Build the single, deterministic DEV8 App + Home Assistant source package.

Pure source-only: no HAOS connection, Docker, Nabto SDK, user credentials,
Supervision operations or install actions.
"""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "genvex-nabto-remote"
HA = ROOT / "experimental/home_assistant/custom_components/genvex_remote"
DIST = ROOT / "dist"
ARCHIVE = DIST / "genvex-remote-dev8-combined.tar.gz"
SUMS = DIST / "DEV8_COMBINED_SHA256SUMS"

APP_VERSION = "0.1.0-dev8"
HA_VERSION = "0.2.0"
MAX_MEMBER_SIZE = 150_000
MAX_TOTAL_SIZE = 2_000_000
REGISTER_ADDRESSES = (
    20, 21, 22, 23, 26, 24, 18, 19, 35, 36, 41, 42,
    53, 40, 114, 115, 50,
)


class InvalidCombinedPackage(ValueError):
    """Invalid source evidence, package layout, digest or release version."""


def _regular(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise InvalidCombinedPackage("Invalid source path")
    size = path.stat().st_size
    if not 1 <= size <= MAX_MEMBER_SIZE:
        raise InvalidCombinedPackage("Invalid source size")
    return path.read_bytes()


def source_files() -> dict[str, bytes]:
    """A strict source allowlist: one Supervisor App and one HA component."""
    app_files = [APP / rel for rel in (
        "Dockerfile", "config.yaml", "run.sh",
    )] + sorted((APP / "runtime").glob("*.py"))
    ha_files = sorted(
        p for p in HA.rglob("*")
        if p.suffix in (".py", ".json") and p.is_file()
    )
    if len(app_files) < 17 or not 10 <= len(ha_files) <= 40:
        raise InvalidCombinedPackage("Incomplete source layout")
    files: dict[str, bytes] = {}
    for path in app_files:
        rel = path.relative_to(APP)
        if rel.parts[0] not in ("runtime", "Dockerfile", "config.yaml", "run.sh"):
            raise InvalidCombinedPackage("Unexpected App source")
        files["genvex_nabto_remote/" + rel.as_posix()] = _regular(path)
    for path in ha_files:
        rel = path.relative_to(HA)
        if not (len(rel.parts) == 1
                or len(rel.parts) == 2 and rel.parts[0] == "translations"):
            raise InvalidCombinedPackage("Unexpected HA source")
        files["custom_components/genvex_remote/" + rel.as_posix()] = _regular(path)

    app_manifest = files["genvex_nabto_remote/config.yaml"].decode("utf-8")
    if (re.search(r'^version: "0\.1\.0-dev8"$', app_manifest, re.MULTILINE) is None
            or "  raw_registers_v3: bool" not in app_manifest
            or "  raw_registers_v3: false" not in app_manifest
            or "host_network: false" not in app_manifest
            or "boot: manual_only" not in app_manifest):
        raise InvalidCombinedPackage("App version/configuration mismatch")
    try:
        manifest = json.loads(files[
            "custom_components/genvex_remote/manifest.json"
        ])
    except (UnicodeError, ValueError):
        raise InvalidCombinedPackage("Invalid HA manifest") from None
    if (manifest.get("version") != HA_VERSION
            or manifest.get("domain") != "genvex_remote"
            or manifest.get("config_flow") is not True):
        raise InvalidCombinedPackage("HA integration version mismatch")

    # The two checked-in runtime copies must be identical before packing.
    spec = importlib.util.spec_from_file_location(
        "dev8_parity_check", ROOT / "scripts/check_remote_runtime_parity.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.check():
        raise InvalidCombinedPackage("App/backend source parity mismatch")
    return dict(sorted(files.items()))


def manifest_for(files: dict[str, bytes]) -> bytes:
    manifest = {
        "release": "GENVEX_REMOTE_DEV8",
        "app_version": APP_VERSION,
        "home_assistant_version": HA_VERSION,
        "snapshot_schema": 3,
        "rpc45_addresses": list(REGISTER_ADDRESSES),
        "files": {
            name: hashlib.sha256(body).hexdigest()
            for name, body in sorted(files.items())
        },
    }
    return (json.dumps(manifest, sort_keys=True, separators=(",", ":"))
            + "\n").encode("utf-8")


def build() -> tuple[Path, str, int]:
    files = source_files()
    files["DEV8_RELEASE_MANIFEST.json"] = manifest_for(files)
    DIST.mkdir(parents=True, exist_ok=True)
    with ARCHIVE.open("wb") as output:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=output, mtime=0,
        ) as compressed:
            with tarfile.open(fileobj=compressed, mode="w",
                              format=tarfile.PAX_FORMAT) as bundle:
                for name, body in sorted(files.items()):
                    info = tarfile.TarInfo(name)
                    info.size = len(body)
                    info.mode = 0o755 if name.endswith("/run.sh") else 0o644
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.mtime = 0
                    bundle.addfile(info, io.BytesIO(body))
    if ARCHIVE.stat().st_size > MAX_TOTAL_SIZE:
        raise InvalidCombinedPackage("Combined archive too large")
    digest = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    SUMS.write_text(f"{digest}  {ARCHIVE.name}\n", encoding="ascii")
    return ARCHIVE, digest, len(files)


def verify(path: Path, expected_sha256: str) -> dict:
    """Validate every regular member, digest, release version and allowlist."""
    if (type(expected_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None
            or path.is_symlink() or not path.is_file()
            or not 100 <= path.stat().st_size <= MAX_TOTAL_SIZE
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256):
        raise InvalidCombinedPackage("Archive checksum/size mismatch")
    try:
        with tarfile.open(path, "r:gz") as bundle:
            members = bundle.getmembers()
            if not 30 <= len(members) <= 90:
                raise InvalidCombinedPackage("Unexpected archive member count")
            seen = {}
            for member in members:
                name = member.name
                pure = PurePosixPath(name)
                parts = pure.parts
                if (not member.isfile() or member.issym() or member.islnk()
                        or name in seen or name != pure.as_posix()
                        or any(p in ("", ".", "..") or p.startswith(".") for p in parts)
                        or len(name) > 200
                        or not 1 <= member.size <= MAX_MEMBER_SIZE
                        or not (
                            name == "DEV8_RELEASE_MANIFEST.json"
                            or parts[0] == "genvex_nabto_remote"
                            and (len(parts) == 2 and parts[1] in (
                                "Dockerfile", "config.yaml", "run.sh",
                            ) or len(parts) == 3 and parts[1] == "runtime"
                                 and parts[2].endswith(".py"))
                            or parts[:2] == ("custom_components", "genvex_remote")
                            and (len(parts) == 3 and parts[2].endswith((".py", ".json"))
                                 or len(parts) == 4
                                 and parts[2] == "translations"
                                 and parts[3].endswith(".json"))
                        )):
                    raise InvalidCombinedPackage("Unexpected archive member")
                seen[name] = bundle.extractfile(member).read()
            if "DEV8_RELEASE_MANIFEST.json" not in seen:
                raise InvalidCombinedPackage("Missing release manifest")
            release = json.loads(seen.pop("DEV8_RELEASE_MANIFEST.json"))
            if (release.get("release") != "GENVEX_REMOTE_DEV8"
                    or release.get("app_version") != APP_VERSION
                    or release.get("home_assistant_version") != HA_VERSION
                    or release.get("snapshot_schema") != 3
                    or release.get("rpc45_addresses") != list(REGISTER_ADDRESSES)
                    or release.get("files") != {
                        k: hashlib.sha256(v).hexdigest()
                        for k, v in sorted(seen.items())
                    }):
                raise InvalidCombinedPackage("Manifest/source mismatch")
            if ("genvex_nabto_remote/config.yaml" not in seen
                    or "custom_components/genvex_remote/manifest.json" not in seen
                    or "genvex_nabto_remote/runtime/raw_registers_v3.py" not in seen
                    or "custom_components/genvex_remote/raw_snapshot_v3.py" not in seen):
                raise InvalidCombinedPackage("Required v3 source absent")
            return release
    except (tarfile.TarError, OSError, json.JSONDecodeError):
        raise InvalidCombinedPackage("Unusable combined archive") from None


if __name__ == "__main__":
    archive, sha, count = build()
    verify(archive, sha)
    print("DEV8_COMBINED_PACKAGE: PASS")
    print("APP_VERSION:", APP_VERSION)
    print("HA_VERSION:", HA_VERSION)
    print("SOURCE_MEMBERS:", count)
    print("SHA256:", sha)
