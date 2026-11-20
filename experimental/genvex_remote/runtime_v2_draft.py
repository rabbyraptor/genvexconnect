"""Explicit, loopback-only opt-in v2 runtime composition for offline tests.

Not shipped inside the HAOS App. Construction creates NO listener, SDK process,
network request, credential store, Home Assistant entity or background task.
An approved caller provides a separately configured read-only v2 snapshot
adapter, and must explicitly call start/stop. No attempt to replace v1 runtime.
"""
from __future__ import annotations

from ipc_auth import IPCAuthError, authorize_read
from polling_service import PollingService
from sensor_model import remote_hostname
from v2_polling_state import V2SnapshotState
from v2_snapshot_bridge import OptInV2SnapshotBridge


class ExperimentalV2Runtime:
    """A single owner of polling, cached snapshot and loopback IPC."""

    def __init__(self, *, device_id: str, adapter: object, token: str,
                 interval_seconds: float = 60, port: int = 0):
        remote_hostname(device_id)
        if (getattr(adapter, "device_id", None) != device_id
                or not callable(getattr(adapter, "poll_once", None))):
            raise ValueError("V2 adapter must match device and support polling")
        try:
            authorize_read(token, token)
        except IPCAuthError:
            raise ValueError("Invalid internal IPC token") from None
        if type(port) is not int or (port != 0 and not 1024 <= port <= 65535):
            raise ValueError("Invalid loopback test port")
        self.state = V2SnapshotState(adapter)
        self.bridge = OptInV2SnapshotBridge(
            state=self.state, device_id=device_id
        )
        self._service = PollingService(
            self.state, interval_seconds=interval_seconds
        )
        self._token = token
        self._port = port
        self._server = None

    @property
    def running(self) -> bool:
        return self._service.running and self._server is not None

    @property
    def local_port(self) -> int | None:
        if self._server is None:
            return None
        return self._server._server.server_port

    async def start(self) -> None:
        """Explicit action; HTTP is *always* 127.0.0.1 (not container public)."""
        if self._server is not None:
            raise RuntimeError("Experimental v2 runtime already started")
        self._server = self.bridge.new_loopback_server(
            token=self._token, port=self._port
        )
        try:
            await self._service.start()
            self._server.start()
        except BaseException:
            await self._service.stop()
            self._server.stop()
            self._server = None
            raise

    async def stop(self) -> None:
        """Stop polling, clear snapshot, and close the listener."""
        await self._service.stop()
        server, self._server = self._server, None
        if server is not None:
            server.stop()
