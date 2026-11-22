"""Age-aware handling of validated remote measurements (no Home Assistant dependency)."""
from __future__ import annotations

from datetime import datetime, timezone

GRACE_SECONDS = 600


def sample_time(snapshot: dict) -> datetime:
    """Return the measurement timestamp after snapshot schema validation."""
    return datetime.fromisoformat(
        snapshot["timestamp_utc"].replace("Z", "+00:00")
    ).astimezone(timezone.utc)


def age_seconds(measured: datetime | None, *, now: datetime | None = None) -> float | None:
    """Age is based on the gateway measurement, never the cache read time."""
    if measured is None:
        return None
    current = now or datetime.now(timezone.utc)
    return max(0.0, (current - measured).total_seconds())


def within_grace(measured: datetime | None, *, now: datetime | None = None) -> bool:
    age = age_seconds(measured, now=now)
    return age is not None and age <= GRACE_SECONDS
