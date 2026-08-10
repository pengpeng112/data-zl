"""Timezone-safe pure helpers shared by identity synchronization."""

from __future__ import annotations

from datetime import datetime, timezone


def as_aware(value: datetime | None) -> datetime | None:
    """Normalize a naive database timestamp to UTC without changing fields."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def is_after_modified_watermark(
    parsed: datetime,
    modified_since: datetime,
    source_tie_key: str,
    watermark_tie_key: str | None,
) -> bool:
    """Compare mixed DB timestamp forms and apply the stable tie-breaker."""
    parsed_aware = as_aware(parsed)
    modified_aware = as_aware(modified_since)
    if parsed_aware is None or modified_aware is None:
        return False
    return parsed_aware > modified_aware or (
        parsed_aware == modified_aware
        and bool(watermark_tie_key)
        and source_tie_key > str(watermark_tie_key)
    )
