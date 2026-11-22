"""HA DataUpdateCoordinator for age-aware, read-only remote sensors."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, POLL_SECONDS
from .freshness import age_seconds, sample_time, within_grace
from .runtime_client import RuntimeUnavailable, SnapshotReader
from .snapshot import InvalidSnapshot, validate_snapshot


class GenvexRemoteCoordinator(DataUpdateCoordinator[dict[str, float]]):
    """Keep a validated measurement through short remote disconnects."""

    def __init__(
        self, hass: HomeAssistant, device_id: str, reader: SnapshotReader,
    ) -> None:
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name=f"{DOMAIN}_{device_id}",
            update_interval=timedelta(seconds=POLL_SECONDS),
        )
        self.device_id = device_id
        self.reader = reader
        self.last_sample_utc: datetime | None = None
        self._last_values: dict[str, float] | None = None

    @property
    def data_age_seconds(self) -> float | None:
        """Elapsed time since the original measurement, not its HTTP retrieval."""
        return age_seconds(self.last_sample_utc)

    async def _async_update_data(self) -> dict[str, float]:
        try:
            payload = await self.reader.async_fetch_snapshot(self.device_id)
            values = validate_snapshot(payload, expected_device_id=self.device_id)
            measured = sample_time(payload)
            # An older cached response must never roll measurements backward.
            if self.last_sample_utc is None or measured > self.last_sample_utc:
                self.last_sample_utc = measured
                self._last_values = values
            if self._last_values is not None and within_grace(self.last_sample_utc):
                return self._last_values
        except (RuntimeUnavailable, InvalidSnapshot, TimeoutError, OSError):
            pass

        if self._last_values is not None and within_grace(self.last_sample_utc):
            return self._last_values
        # CoordinatorEntity automatically becomes unavailable after grace expires.
        raise UpdateFailed("Genvex remote readings are unavailable")
