
from __future__ import annotations

from datetime import UTC, datetime


def to_utc_timestamp(value: datetime) -> float:
    """Normalize naive/aware datetimes to UTC timestamp for safe comparisons."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC).timestamp()
    return value.astimezone(UTC).timestamp()


def is_expired(expires_at: datetime, *, now: datetime | None = None) -> bool:
    current = now or datetime.now(UTC)
    return to_utc_timestamp(expires_at) < to_utc_timestamp(current)

