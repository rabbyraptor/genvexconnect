"""Opt-in QEMU subprocess adapter: one SDK v2 marker -> validated snapshot.

Uses existing, separately authorized encrypted profile and settings-stdin protocol.
No SDK is loaded or subprocess started on import. This module is not bundled in
the installed HAOS App and is never an automatic conversion of the v1 runtime.
"""
from __future__ import annotations

import asyncio
import json

from sdk_snapshot_adapter import (
    SDKSnapshotAdapter, SDKSnapshotError, _read_probe_output_bounded,
)
from snapshot_v2_draft import parse_v2

_MARKER_V2 = "GENVEX_READONLY_SNAPSHOT_V2="
_MAX_RESULT_BYTES = 4096
_MAX_OUTPUT_BYTES = 32768


def parse_v2_probe_output(output: bytes, *, device_id: str) -> dict:
    """Validate exactly one fresh v2 marker, never echo SDK output."""
    try:
        if type(output) is not bytes or len(output) > _MAX_OUTPUT_BYTES:
            raise ValueError
        lines = output.decode("utf-8", "strict").splitlines()
        markers = [line[len(_MARKER_V2):] for line in lines
                   if line.startswith(_MARKER_V2)]
        if len(markers) != 1 or len(markers[0]) > _MAX_RESULT_BYTES:
            raise ValueError
        document = json.loads(markers[0])
        parse_v2(document, expected_device_id=device_id)
        return document
    except (ValueError, UnicodeError, TypeError):
        raise SDKSnapshotError("No valid SDK v2 snapshot") from None


class SDKSnapshotV2Adapter(SDKSnapshotAdapter):
    """Isolated v2 probe: no retries; subprocess secrets only on stdin.

    The configured probe file MUST be the separately tested v2 script.
    This adapter never changes the parent v1 adapter or its snapshot parser.
    """

    async def poll_once(self) -> dict:
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
                async with asyncio.timeout(self._timeout):
                    out = await _read_probe_output_bounded(
                        proc,
                        (self._identity + "\n" + self.hostname + "\n"
                         + self._unlock_secret + "\n").encode("utf-8"),
                    )
                if proc.returncode != 0:
                    raise SDKSnapshotError("SDK v2 read failed")
                return parse_v2_probe_output(out, device_id=self.device_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                raise SDKSnapshotError("SDK v2 read failed") from None
            finally:
                if proc is not None and proc.returncode is None:
                    proc.kill()
                    if proc.stdout is not None:
                        while await proc.stdout.read(8192):
                            pass
                    await proc.wait()
