"""Opt-in persistent read-only Micro Nabto SDK adapter.

NOT wired to the live DEV3 App. An isolated QEMU child owns one Nabto
session and handles multiple serial RPC45 requests over private stdio.
Credential data never appears in arguments, environment or error messages.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sdk_snapshot_adapter import SDKSnapshotError
from raw_registers_v3 import parse_raw_v3
from raw_snapshot_v4 import parse_v4
from sensor_model import remote_hostname
from snapshot_contract import parse_snapshot

_READY = b"GENVEX_PERSISTENT_READY="
_RESULT = b"GENVEX_PERSISTENT_RESULT="
_MAX_FRAME = 4096


class PersistentSDKSnapshotAdapter:
    """Keep session after one RPC error; recycle after two consecutive errors.

    Each error is returned to SnapshotState without an immediate retry.
    The next scheduled poll either reuses the existing worker/session or
    starts a new one if the worker was recycled. Timeout, cancellation, and
    invalid output kill/reap the worker. Call aclose() on service shutdown.
    """

    def __init__(
        self, *, device_id: str, identity: str, unlock_secret: str,
        profile_dir: str, worker_file: str,
        timeout_seconds: float = 85.0,
        startup_timeout_seconds: float = 30.0,
        raw_registers_v3: bool = False,
        fan_level_v4: bool = False,
        command: tuple[str, ...] | None = None,
    ):
        self.device_id = device_id
        self.hostname = remote_hostname(device_id)
        if (type(identity) is not str or not identity
                or any(c in identity for c in "\r\n\x00")):
            raise ValueError("Invalid SDK identity")
        if (type(unlock_secret) is not str or not unlock_secret
                or any(c in unlock_secret for c in "\r\n\x00")):
            raise ValueError("Invalid SDK secret")
        if (type(timeout_seconds) not in (int, float)
                or not 0 < timeout_seconds <= 120
                or type(startup_timeout_seconds) not in (int, float)
                or not 0 < startup_timeout_seconds <= 120):
            raise ValueError("Invalid timeout")
        if type(raw_registers_v3) is not bool:
            raise ValueError("Invalid raw v3 flag")
        if not Path(profile_dir).is_dir() or not Path(worker_file).is_file():
            raise ValueError("Missing SDK profile or worker")
        self._identity = identity
        self._secret = unlock_secret
        self._profile_dir = profile_dir
        if type(fan_level_v4) is not bool or (fan_level_v4 and not raw_registers_v3):
            raise ValueError("Fan level v4 requires raw v3")
        self._raw_registers_v3 = raw_registers_v3
        self._fan_level_v4 = fan_level_v4
        self._timeout = float(timeout_seconds)
        self._startup_timeout = float(startup_timeout_seconds)
        self._command = command or (
            "/usr/local/bin/qemu-x86_64-static",
            "-L", "/opt/x86_64-sysroot",
            "-E", "LD_LIBRARY_PATH=/opt/x86_64-sysroot/usr/local/lib",
            "/opt/x86_64-sysroot/usr/local/bin/python3",
            worker_file, "--serve-stdio",
        )
        self._lock = asyncio.Lock()
        self._proc: asyncio.subprocess.Process | None = None
        self._consecutive_rpc_errors = 0

    @staticmethod
    async def _frame(proc: asyncio.subprocess.Process, prefix: bytes) -> dict:
        if proc.stdout is None:
            raise ValueError("Missing stdout")
        raw = await proc.stdout.readline()
        if (not raw or len(raw) > _MAX_FRAME or not raw.endswith(b"\n")
                or not raw.startswith(prefix)):
            raise ValueError("Invalid SDK worker frame")
        data = json.loads(raw[len(prefix):])
        if type(data) is not dict:
            raise ValueError("Invalid worker response")
        return data

    async def _shutdown_worker(self, *, graceful: bool = False) -> None:
        proc, self._proc = self._proc, None
        self._consecutive_rpc_errors = 0
        if proc is None:
            return
        if graceful and proc.returncode is None and proc.stdin is not None:
            try:
                proc.stdin.write(b"CLOSE\n")
                async with asyncio.timeout(2):
                    await proc.stdin.drain()
                    await proc.wait()
            except Exception:
                pass
        if proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
        waiter = asyncio.create_task(proc.wait())
        try:
            await asyncio.shield(waiter)
        except asyncio.CancelledError:
            await asyncio.shield(waiter)
            raise
        finally:
            if proc.stdin is not None:
                proc.stdin.close()

    async def _ensure_worker(self) -> None:
        if self._proc is not None:
            if self._proc.returncode is None:
                return
            # A previously valid SDK process can exit between scheduled
            # polls. Never reuse its closed stdio or retain an old error
            # counter when starting a replacement session.
            await self._shutdown_worker()
        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": "/tmp",
            "GENVEX_NABTO_PROFILE": self._profile_dir,
        }
        try:
            self._proc = await asyncio.create_subprocess_exec(
                *self._command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=env,
                limit=8192,
            )
            proc = self._proc
            if proc.stdin is None:
                raise ValueError("Missing stdin")
            credentials = json.dumps({
                "identity": self._identity,
                "host": self.hostname,
                "passphrase": self._secret,
            }, separators=(",", ":")).encode() + b"\n"
            if len(credentials) > 4096:
                raise ValueError("Credential payload too large")
            async with asyncio.timeout(self._startup_timeout):
                proc.stdin.write(credentials)
                await proc.stdin.drain()
                ready = await self._frame(proc, _READY)
            if ready == {"ok": True}:
                return
            if (set(ready) == {"ok", "stage"} and ready["ok"] is False
                    and type(ready["stage"]) is str
                    and ready["stage"] in SDKSnapshotError.ALLOWED):
                raise SDKSnapshotError(ready["stage"])
            raise ValueError("Invalid startup frame")
        except BaseException:
            await self._shutdown_worker()
            raise

    async def poll_once(self) -> dict:
        async with self._lock:
            try:
                await self._ensure_worker()
                proc = self._proc
                if proc is None or proc.stdin is None:
                    raise ValueError("Worker missing")
                async with asyncio.timeout(self._timeout):
                    proc.stdin.write(b"POLL4\n" if self._fan_level_v4 else
                                     b"POLL3\n" if self._raw_registers_v3 else b"POLL\n")
                    await proc.stdin.drain()
                    payload = await self._frame(proc, _RESULT)
                if set(payload) == {"ok", "snapshot"} and payload["ok"] is True:
                    snapshot = payload["snapshot"]
                    if self._fan_level_v4:
                        parse_v4(snapshot, expected_device_id=self.device_id)
                    elif self._raw_registers_v3:
                        parse_raw_v3(snapshot, expected_device_id=self.device_id)
                    else:
                        parse_snapshot(snapshot, expected_device_id=self.device_id)
                    self._consecutive_rpc_errors = 0
                    return snapshot
                if (set(payload) == {"ok", "status", "elapsed_ms"}
                        and payload["ok"] is False
                        and type(payload["status"]) is int
                        and 0 <= payload["status"] <= 100000
                        and type(payload["elapsed_ms"]) is int
                        and 0 <= payload["elapsed_ms"] <= 120000):
                    if payload["status"] == 0:
                        await self._shutdown_worker()
                        raise SDKSnapshotError("SDK_RESPONSE_INVALID")
                    self._consecutive_rpc_errors += 1
                    if self._consecutive_rpc_errors >= 2:
                        await self._shutdown_worker(graceful=True)
                    raise SDKSnapshotError(
                        "SDK_RPC45_FAILED",
                        rpc_status=payload["status"],
                        elapsed_ms=payload["elapsed_ms"],
                    )
                raise ValueError("Invalid result frame")
            except asyncio.CancelledError:
                await self._shutdown_worker()
                raise
            except TimeoutError:
                await self._shutdown_worker()
                raise SDKSnapshotError("SDK_TIMEOUT") from None
            except SDKSnapshotError:
                raise
            except Exception:
                await self._shutdown_worker()
                raise SDKSnapshotError("SDK_PROCESS_FAILURE") from None

    async def aclose(self) -> None:
        async with self._lock:
            await self._shutdown_worker(graceful=True)
