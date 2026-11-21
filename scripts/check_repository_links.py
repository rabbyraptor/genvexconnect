#!/usr/bin/env python3
"""Static repo-hygiene check: local docs links and retired script references."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ARCHIVED_SCRIPTS = {
    "audit_haos_remote_private_storage_v1.sh",
    "audit_haos_v2_ipc_supervisor_state_v1.sh",
    "run_haos_ipc_two_container_test.sh",
    "run_haos_live_rpc_to_ipc_test_v1.sh",
    *(f"run_haos_remote_install_preflight_v{i}.sh" for i in range(1, 7)),
    "run_haos_sdk_adapter_offline_v1.sh",
    "run_haos_sdk_adapter_offline_v2.sh",
    "run_haos_v2_offline_preflight_v1.sh",
    "run_haos_v2_runtime_offline_v3.sh",
    "run_haos_v2_runtime_offline_v4.sh",
}
LOCAL_LINK = re.compile(r"\]\(([^)]+)\)")


def markdown_paths() -> list[Path]:
    paths = [ROOT / "README.md", ROOT / "scripts/README.md",
             ROOT / "genvex-nabto-remote/DOCS.md",
             ROOT / "experimental/home_assistant/README.md"]
    paths.extend((ROOT / "docs").glob("*.md"))
    paths.append(ROOT / "docs/archive/README.md")
    return [p for p in paths if p.is_file()]


def check() -> list[str]:
    errors: list[str] = []
    for path in markdown_paths():
        text = path.read_text(encoding="utf-8")
        for match in LOCAL_LINK.finditer(text):
            raw = match.group(1).strip()
            if raw.startswith("<") and ">" in raw:
                raw = raw[1:raw.index(">")]
            else:
                raw = raw.split(" ", 1)[0]
            url = urlsplit(raw)
            if url.scheme or url.netloc or not url.path or url.path.startswith("/"):
                continue
            if not (path.parent / unquote(url.path)).exists():
                errors.append(f"{path.relative_to(ROOT)}: missing local link {raw}")
    # All test and workflow references must point to the archived file paths.
    extensions = {".py", ".sh", ".yaml", ".yml"}
    for folder in (".github/workflows", "scripts", "experimental", "genvex-nabto-remote", "tests"):
        base = ROOT / folder
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.suffix not in extensions or not path.is_file():
                continue
            if "archive" in path.relative_to(ROOT).parts or path == Path(__file__):
                continue
            content = path.read_text(encoding="utf-8")
            for name in ARCHIVED_SCRIPTS:
                if f"scripts/{name}" in content:
                    errors.append(f"{path.relative_to(ROOT)}: old script path scripts/{name}")
    for name in ARCHIVED_SCRIPTS:
        if not (ROOT / "scripts/archive" / name).is_file():
            errors.append(f"missing archived script: {name}")
        if (ROOT / "scripts" / name).exists():
            errors.append(f"retired script still present at active path: {name}")
    return errors


if __name__ == "__main__":
    issues = check()
    if issues:
        print("\n".join("FAIL: " + i for i in issues))
        raise SystemExit(1)
    print("PASS: current docs links, archived scripts and code references")
