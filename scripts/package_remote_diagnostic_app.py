#!/usr/bin/env python3
"""Make a reviewed local Home Assistant App source archive (no credentials).

Creates only a source archive: it does not build/install/start an App.
Use only versioned repository sources, never an on-host /data profile.
"""
from __future__ import annotations

import hashlib
import gzip
from pathlib import Path
import stat
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "genvex-nabto-remote"
DEST = ROOT / "dist"
ARCHIVE = DEST / "genvex-nabto-remote-local-app-source.tar.gz"
APP_DIR = "genvex_nabto_remote"
REQUIRED = ("Dockerfile", "config.yaml", "run.sh")
MAX_SOURCE_BYTES = 1_000_000


def archive_sources() -> list[Path]:
    sources = [SOURCE / name for name in REQUIRED]
    runtime = sorted((SOURCE / "runtime").glob("*.py"))
    if len(runtime) < 5:
        raise RuntimeError("Missing runtime modules")
    sources.extend(runtime)
    for path in sources:
        rel = path.relative_to(SOURCE)
        if not path.is_file() or path.is_symlink():
            raise RuntimeError("Not a regular source file")
        if path.stat().st_size > MAX_SOURCE_BYTES:
            raise RuntimeError("Source file too large")
        if any(part.startswith(".") for part in rel.parts):
            raise RuntimeError("Hidden source path")
        if path.suffix not in (".py", ".yaml", ".sh", ""):
            raise RuntimeError("Unexpected source extension")
    return sources


def create_archive() -> Path:
    sources = archive_sources()
    DEST.mkdir(parents=True, exist_ok=True)
    # No gzip filename/current-time header: identical source produces identical bytes.
    with ARCHIVE.open("wb") as output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for source in sources:
                rel = source.relative_to(SOURCE)
                info = archive.gettarinfo(str(source), arcname=f"{APP_DIR}/{rel.as_posix()}")
                if not info.isfile():
                    raise RuntimeError("Cannot package a nonregular file")
                # Stable, owner-only modes within App source; run.sh executable.
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mtime = 0
                info.mode = 0o755 if rel.as_posix() == "run.sh" else 0o644
                with source.open("rb") as stream:
                    archive.addfile(info, stream)
    checksum = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    (DEST / "APP_SOURCE_SHA256SUMS").write_text(
        checksum + "  " + ARCHIVE.name + "\n", encoding="ascii"
    )
    return ARCHIVE


if __name__ == "__main__":
    path = create_archive()
    print("PASS: source-only local App archive created (no credentials)")
    print("Archive:", path.relative_to(ROOT))
