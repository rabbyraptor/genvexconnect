"""Isolated candidate adapter: one QEMU Nabto RPC45 probe -> fresh snapshot.

No service starts on import. The caller supplies an already-authorized
profile folder and unlock secret; neither is stored here. This is not an
enrollment path, persistent credential manager or production App yet.
"""
from __future__ import annotations

import asyncio
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
    """The isolated legacy client did not return one valid read-only batch."""


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
        raise SDKSnapshotError("No valid SDK snapshot") from None


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
                    raise SDKSnapshotError("SDK read failed")
                return parse_probe_output(out, device_id=self.device_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                raise SDKSnapshotError("SDK read failed") from None
            finally:
                if proc is not None and proc.returncode is None:
                    proc.kill()
                    # Drain/discard the bounded pipe after killing the child:
                    # waiting alone may hang if stdout backpressure is active.
                    if proc.stdout is not None:
                        while await proc.stdout.read(8192):
                            pass
                    await proc.wait()
