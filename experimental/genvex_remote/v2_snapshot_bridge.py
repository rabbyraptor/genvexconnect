"""Inert opt-in v2 -> v1/v2 snapshot provider bridge for loopback tests.

Does not replace v1 runtime or start a listener, poller or Nabto session.
The caller must separately refresh an injected v2 state and explicitly start
the returned loopback-only HTTP server. One RPC result serves both contracts.
"""
from __future__ import annotations

from polling_http_server_v2_draft import ExperimentalV2HTTPServer
from sensor_model import remote_hostname
from snapshot_contract import SnapshotError
from snapshot_v2_draft import parse_v2
from v2_polling_state import V2SnapshotState


class OptInV2SnapshotBridge:
    """Project one fresh validated seven-value state to both versioned APIs."""

    def __init__(self, *, state: V2SnapshotState, device_id: str):
        remote_hostname(device_id)
        if not isinstance(state, V2SnapshotState) or state.device_id != device_id:
            raise ValueError("V2 state and device identity must match")
        self._state = state
        self.device_id = device_id

    def current_v2(self) -> dict | None:
        """One detached v2 payload or unavailable; no I/O."""
        return self._state.current()

    def current_v1(self) -> dict | None:
        """Project the five legacy keys without new RPCs or optional metadata."""
        payload = self.current_v2()
        if payload is None:
            return None
        try:
            baseline, _fans = parse_v2(
                payload, expected_device_id=self.device_id
            )
        except (SnapshotError, ValueError, TypeError):
            return None
        return {
            "schema_version": 1,
            "device_id": self.device_id,
            "timestamp_utc": payload["timestamp_utc"],
            "health": "ok",
            "values": dict(baseline),
        }

    def new_loopback_server(
        self, *, token: str, port: int = 0
    ) -> ExperimentalV2HTTPServer:
        """Construct but do not start a test-only loopback HTTP listener."""
        return ExperimentalV2HTTPServer(
            bind_host="127.0.0.1",
            port=port,
            token=token,
            device_id=self.device_id,
            snapshot_provider=self.current_v1,
            v2_snapshot_provider=self.current_v2,
        )
