"""Offline-only primitives for a future allowlisted HAOS development MCP.

No MCP listener, Docker socket, shell, live App or deployment is accessed here.
An approved separate service may reuse these validators, but MUST enforce
authorization and isolate execution before exposing any write/test endpoint.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

RUNTIME = Path("genvex-nabto-remote/runtime")
ALLOWED_FILES = frozenset({
    "app_bootstrap.py", "ipc_auth.py", "persistent_rpc45_worker.py",
    "persistent_sdk_adapter.py", "polling_http_server.py",
    "polling_runtime.py", "polling_service.py", "polling_worker.py",
    "sdk_snapshot_adapter.py", "sensor_model.py", "snapshot_api.py",
    "snapshot_contract.py", "snapshot_state.py",
})
MAX_SOURCE_BYTES = 131072
_TESTS = {
    "remote_app": ("genvex-nabto-remote/tests", "test_*.py"),
    "remote_core_contract": ("experimental/home_assistant/tests", "test_*.py"),
    "remote_v2_projection": ("experimental/genvex_remote", "test_ha_v2_projection.py"),
}


class DevMCPRejected(ValueError):
    """Sanitized input, integrity or execution rejection."""


@dataclass(frozen=True)
class PatchPreview:
    filename: str
    old_sha256: str
    new_sha256: str
    old_size: int
    new_size: int


@dataclass(frozen=True)
class OfflineTestResult:
    test_id: str
    passed: bool
    exit_code: int
    test_count: int | None


def _repo_root(root: Path) -> Path:
    """Require an existing checked-out source tree, not an active container."""
    try:
        path = Path(root).resolve(strict=True)
        expected = path / RUNTIME
        if not expected.is_dir() or expected.is_symlink():
            raise DevMCPRejected("Invalid source checkout")
        return path
    except (OSError, ValueError, TypeError):
        raise DevMCPRejected("Invalid source checkout") from None


def preview_runtime_patch(
    *, root: Path, filename: str, expected_sha256: str, replacement: str,
) -> PatchPreview:
    """Validate an exact source SHA and Python syntax. NEVER change the file."""
    if type(filename) is not str or filename not in ALLOWED_FILES:
        raise DevMCPRejected("Runtime filename not allowlisted")
    if (type(expected_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None):
        raise DevMCPRejected("Invalid expected SHA256")
    if type(replacement) is not str:
        raise DevMCPRejected("Invalid replacement source")
    try:
        changed = replacement.encode("utf-8", "strict")
    except UnicodeError:
        raise DevMCPRejected("Invalid replacement source") from None
    if not changed or len(changed) > MAX_SOURCE_BYTES or b"\x00" in changed:
        raise DevMCPRejected("Invalid replacement source")

    checkout = _repo_root(root)
    target = checkout / RUNTIME / filename
    try:
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            meta = os.fstat(fd)
            if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
                raise DevMCPRejected("Unsafe source file")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                original = stream.read(MAX_SOURCE_BYTES + 1)
        finally:
            os.close(fd)
    except OSError:
        raise DevMCPRejected("Unsafe source file") from None
    if len(original) > MAX_SOURCE_BYTES:
        raise DevMCPRejected("Unsafe source file")
    old_hash = hashlib.sha256(original).hexdigest()
    if old_hash != expected_sha256:
        raise DevMCPRejected("Source changed since inspection")
    try:
        ast.parse(replacement, filename=filename)
    except (SyntaxError, ValueError, RecursionError):
        raise DevMCPRejected("Invalid Python source") from None
    return PatchPreview(
        filename, old_hash, hashlib.sha256(changed).hexdigest(),
        len(original), len(changed),
    )


def run_allowlisted_offline_test(
    *, root: Path, test_id: str, timeout_seconds: int = 90,
) -> OfflineTestResult:
    """Run a fixed unittest selector without a shell. No raw logs returned.

    The calling MCP implementation must run this in a no-network, unprivileged
    container without production credentials, mounts or Docker access.
    """
    if type(test_id) is not str or test_id not in _TESTS:
        raise DevMCPRejected("Test selector not allowlisted")
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 120:
        raise DevMCPRejected("Invalid test deadline")
    checkout = _repo_root(root)
    relative, pattern = _TESTS[test_id]
    tests = checkout / relative
    if not tests.is_dir() or tests.is_symlink():
        raise DevMCPRejected("Missing offline tests")
    command = (
        sys.executable, "-B", "-m", "unittest", "discover",
        "-s", relative, "-p", pattern, "-v",
    )
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": "/tmp",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    try:
        with tempfile.TemporaryFile() as output:
            completed = subprocess.run(
                command, cwd=checkout, env=env, stdin=subprocess.DEVNULL,
                stdout=output, stderr=subprocess.STDOUT,
                timeout=timeout_seconds, check=False,
            )
            length = output.tell()
            output.seek(max(0, length - 8192))
            tail = output.read(8192).decode("utf-8", "replace")
    except (OSError, subprocess.TimeoutExpired):
        raise DevMCPRejected("Offline test unavailable") from None
    match = re.search(r"Ran (\d+) tests? in [\d.]+s", tail)
    return OfflineTestResult(
        test_id, completed.returncode == 0, completed.returncode,
        int(match.group(1)) if match else None,
    )
