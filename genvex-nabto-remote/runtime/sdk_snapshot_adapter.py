"""Isolated candidate adapter: one QEMU Nabto RPC45 probe -> fresh snapshot.

No service starts on import. The caller supplies an already-authorized
profile folder and unlock secret; neither is stored here. This is not an
enrollment path, persistent credential manager or production App yet.
"""
from __future__ import annotations

import asyncio
import ast
import json
from pathlib import Path

from sensor_model import remote_hostname
from snapshot_contract import parse_snapshot

_MARKER = "GENVEX_READONLY_SNAPSHOT="
_LAUNCH = r"""
import io, json, runpy, sys
identity = sys.stdin.readline().rstrip("\r\n")
host = sys.stdin.readline().rstrip("\r\n")
secret = sys.stdin.readline().rstrip("\r\n")
if not identity or not host or not secret:
    raise SystemExit("Missing probe settings")
sys.stdin = io.StringIO(json.dumps({
    "identity": identity, "host": host, "passphrase": secret
}) + "\n")
probe = sys.argv[1]
sys.argv = [probe, "--settings-stdin"]
runpy.run_path(probe, run_name="__main__")
"""


class SDKSnapshotError(Exception):
    """Only a fixed, non-sensitive failure category may leave the SDK adapter."""

    ALLOWED = frozenset({
        "SDK_PROCESS_FAILURE", "SDK_TIMEOUT", "SDK_STARTUP_FAILED",
        "SDK_RESOURCES_FAILED", "SDK_SESSION_FAILED", "SDK_XML_FAILED",
        "SDK_RPC45_FAILED", "SDK_RESPONSE_INVALID", "SDK_CLOSE_FAILED",
        "SDK_EARLY_EXIT", "SDK_SNAPSHOT_INVALID",
    })

    def __init__(self, code="SDK_PROCESS_FAILURE", *, rpc_status=None, elapsed_ms=None, rpc_events=None,
                 session_status=None):
        self.code = code if code in self.ALLOWED else "SDK_PROCESS_FAILURE"
        # Only bounded integers extracted from exact SDK stage markers are
        # allowed to reach the optional operator diagnostic view.
        self.session_status = (session_status if type(session_status) is int
                               and 0 <= session_status <= 100000 else None)
        self.rpc_status = rpc_status if type(rpc_status) is int and 0 <= rpc_status <= 100000 else None
        self.elapsed_ms = elapsed_ms if type(elapsed_ms) is int and 0 <= elapsed_ms <= 120000 else None
        self.rpc_events = tuple(rpc_events) if isinstance(rpc_events, tuple) and len(rpc_events) <= 8 and all(type(v) is int and 0 <= v <= 10000000 for v in rpc_events) else ()
        super().__init__(self.code)


def parse_session_diagnostics(output: bytes) -> int | None:
    """Allow exactly one bounded numeric SDK session return code, no raw text."""
    if len(output) > _MAX_PROBE_OUTPUT_BYTES:
        return None
    try:
        lines = output.decode("utf-8", "strict").splitlines()
    except UnicodeError:
        return None
    matches = [line[len("Profile session:"):].strip()
               for line in lines if line.startswith("Profile session:")]
    if len(matches) != 1:
        return None
    value = matches[0]
    if not value or len(value) > 8 or not value.isascii() or not value.isdecimal():
        return None
    status = int(value)
    return status if status <= 100000 else None


def parse_rpc_diagnostics(output: bytes) -> tuple[int | None, int | None]:
    """Extract only exact, bounded numeric RPC markers; never return raw output."""
    if len(output) > _MAX_PROBE_OUTPUT_BYTES:
        return None, None
    try:
        lines = output.decode("utf-8", "strict").splitlines()
    except UnicodeError:
        return None, None

    def number(prefix: str, limit: int) -> int | None:
        found = [line[len(prefix):].strip() for line in lines if line.startswith(prefix)]
        if len(found) != 1:
            return None
        raw = found[0]
        if not raw or len(raw) > 8 or not raw.isascii() or not raw.isdecimal():
            return None
        value = int(raw)
        return value if value <= limit else None

    return number("Batch RPC status:", 100000), number("RPC elapsed_ms:", 120000)



def parse_rpc_events(output: bytes) -> tuple[int, ...]:
    """Allowlist numeric codes from the probe's already-redacted diagnostic.

    This is *not* the original vendor JSON. The probe emits only
    ('ERROR_JSON', [integer codes]) or ('NO_JSON_DIAGNOSTIC', []).
    """
    if len(output) > _MAX_PROBE_OUTPUT_BYTES:
        return ()
    try:
        lines = output.decode("utf-8", "strict").splitlines()
    except UnicodeError:
        return ()
    markers = [line[len("Diagnostic: "):] for line in lines
               if line.startswith("Diagnostic: ")]
    if len(markers) != 1 or len(markers[0]) > 160:
        return ()
    try:
        kind, codes = ast.literal_eval(markers[0])
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return ()
    if kind != "ERROR_JSON" or type(codes) is not list or len(codes) > 8:
        return ()
    if any(type(v) is not int or not 0 <= v <= 10000000 for v in codes):
        return ()
    if codes != sorted(set(codes)):
        return ()
    return tuple(codes)


def classify_probe_failure(output: bytes) -> str:
    """Read only literal stage markers; never echo the raw SDK output."""
    try:
        lines = output.decode("utf-8", "strict").splitlines()
    except UnicodeError:
        return "SDK_PROCESS_FAILURE"
    stages = (
        ("SDK startup:", "SDK_STARTUP_FAILED"),
        ("Resources:", "SDK_RESOURCES_FAILED"),
        ("Profile session:", "SDK_SESSION_FAILED"),
        ("Candidate XML registered:", "SDK_XML_FAILED"),
        ("Batch RPC status:", "SDK_RPC45_FAILED"),
        ("Session close:", "SDK_CLOSE_FAILED"),
        ("SDK shutdown:", "SDK_CLOSE_FAILED"),
    )
    for prefix, code in stages:
        for line in lines:
            if line.startswith(prefix):
                number = line[len(prefix):].strip()
                if number.isascii() and number.isdecimal() and int(number) != 0:
                    return code
    if any(line.startswith("Batch RPC status: 0") for line in lines):
        return "SDK_RESPONSE_INVALID"
    return "SDK_EARLY_EXIT"


def parse_probe_output(output: bytes, *, device_id: str) -> dict:
    """Accept exactly one complete validated marker; ignore diagnostic lines."""
    try:
        if len(output) > 32768:
            raise ValueError
        lines = output.decode("utf-8", "strict").splitlines()
        markers = [line[len(_MARKER):] for line in lines if line.startswith(_MARKER)]
        if len(markers) != 1 or len(markers[0]) > 4096:
            raise ValueError
        snapshot = json.loads(markers[0])
        parse_snapshot(snapshot, expected_device_id=device_id)
        return snapshot
    except (ValueError, UnicodeError, TypeError):
        raise SDKSnapshotError("SDK_SNAPSHOT_INVALID") from None


_MAX_PROBE_OUTPUT_BYTES = 32768


async def _read_probe_output_bounded(proc: asyncio.subprocess.Process, payload: bytes) -> bytes:
    """Stream stdout with a hard cap, before allocating the complete result."""
    if proc.stdin is None or proc.stdout is None:
        raise SDKSnapshotError("SDK pipe unavailable")
    proc.stdin.write(payload)
    await proc.stdin.drain()
    proc.stdin.close()
    await proc.stdin.wait_closed()

    output = bytearray()
    while True:
        part = await proc.stdout.read(min(4096, _MAX_PROBE_OUTPUT_BYTES + 1 - len(output)))
        if not part:
            break
        output.extend(part)
        if len(output) > _MAX_PROBE_OUTPUT_BYTES:
            raise SDKSnapshotError("SDK output too large")
    await proc.wait()
    return bytes(output)


class SDKSnapshotAdapter:
    """Async single-flight subprocess adapter for the *existing* test probe.

    SDK x86_64/QEMU is not loaded into native aarch64 Home Assistant.
    Password is passed via subprocess stdin, not argv/environment/logging.
    """

    def __init__(self, *, device_id: str, identity: str, unlock_secret: str,
                 profile_dir: str, probe_file: str,
                 timeout_seconds: float = 85.0,
                 command: tuple[str, ...] | None = None):
        self.device_id = device_id
        self.hostname = remote_hostname(device_id)
        if not isinstance(identity, str) or not identity or any(c in identity for c in "\r\n\x00"):
            raise ValueError("Invalid SDK identity")
        if not isinstance(unlock_secret, str) or not unlock_secret or any(c in unlock_secret for c in "\r\n\x00"):
            raise ValueError("Invalid SDK unlock secret")
        if not isinstance(timeout_seconds, (float, int)) or isinstance(timeout_seconds, bool) or not 1 <= timeout_seconds <= 120:
            raise ValueError("Invalid SDK timeout")
        if not Path(profile_dir).is_dir() or not Path(probe_file).is_file():
            raise ValueError("Missing isolated SDK profile or probe file")
        self._identity = identity
        self._unlock_secret = unlock_secret
        self._profile_dir = profile_dir
        self._probe_file = probe_file
        self._timeout = float(timeout_seconds)
        self._command = command or (
            "/usr/local/bin/qemu-x86_64-static",
            "-L", "/opt/x86_64-sysroot",
            "-E", "LD_LIBRARY_PATH=/opt/x86_64-sysroot/usr/local/lib",
            "/opt/x86_64-sysroot/usr/local/bin/python3",
            "-c", _LAUNCH, probe_file,
        )
        self._lock = asyncio.Lock()

    async def poll_once(self) -> dict:
        """Do one authorized read, validate, and kill/wait on timeout/cancel."""
        async with self._lock:
            env = {
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "HOME": "/tmp",
                "GENVEX_NABTO_PROFILE": self._profile_dir,
            }
            proc = None
            try:
                proc = await asyncio.create_subprocess_exec(
                    *self._command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                    env=env,
                )
                # No secret in process argv, shell, environment or returned errors.
                async with asyncio.timeout(self._timeout):
                    out = await _read_probe_output_bounded(
                        proc,
                        (self._identity + "\n" + self.hostname + "\n"
                         + self._unlock_secret + "\n").encode("utf-8")
                    )
                if proc.returncode != 0:
                    rpc_status, elapsed_ms = parse_rpc_diagnostics(out)
                    raise SDKSnapshotError(
                        classify_probe_failure(out),
                        rpc_status=rpc_status,
                        elapsed_ms=elapsed_ms,
                        rpc_events=parse_rpc_events(out),
                        session_status=parse_session_diagnostics(out),
                    )
                return parse_probe_output(out, device_id=self.device_id)
            except asyncio.CancelledError:
                raise
            except SDKSnapshotError:
                raise
            except TimeoutError:
                raise SDKSnapshotError("SDK_TIMEOUT") from None
            except Exception:
                raise SDKSnapshotError("SDK_PROCESS_FAILURE") from None
            finally:
                if proc is not None and proc.returncode is None:
                    proc.kill()
                    # Drain/discard the bounded pipe after killing the child:
                    # waiting alone may hang if stdout backpressure is active.
                    if proc.stdout is not None:
                        while await proc.stdout.read(8192):
                            pass
                    await proc.wait()
