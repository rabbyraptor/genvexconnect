"""HA DataUpdateCoordinator for the five remote, read-only sensors."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, POLL_SECONDS
from .runtime_client import RuntimeUnavailable, SnapshotReader
from .snapshot import InvalidSnapshot, validate_snapshot


class GenvexRemoteCoordinator(DataUpdateCoordinator[dict[str, float]]):
    """Update all five sensor entities from one atomic validated response."""

    def __init__(
        self, hass: HomeAssistant, device_id: str, reader: SnapshotReader,
    ) -> None:
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=f"{DOMAIN}_{device_id}",
            update_interval=timedelta(seconds=POLL_SECONDS),
        )
        self.device_id = device_id
        self.reader = reader

    async def _async_update_data(self) -> dict[str, float]:
        try:
            payload = await self.reader.async_fetch_snapshot(self.device_id)
            return validate_snapshot(payload, expected_device_id=self.device_id)
        except (RuntimeUnavailable, InvalidSnapshot, TimeoutError, OSError) as exc:
            raise UpdateFailed("Genvex remote readings are unavailable") from exc
