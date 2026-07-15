"""Write normalized ops/connection/dict events (never store secrets)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..models.ops_tool import OpsEventLog
from .data_masking import mask_sensitive


def log_event(
    db: Session,
    *,
    module: str,
    entity_type: str,
    entity_ref: str,
    action: str,
    operator: str | None = None,
    status: str | None = None,
    target_connection_id: int | None = None,
    target_database_key: str | None = None,
    target_source_code: str | None = None,
    correlation_id: str | None = None,
    batch_code: str | None = None,
    affected_count: int | None = None,
    duration_ms: int | None = None,
    error_code: str | None = None,
    summary_masked: str | None = None,
    detail: dict[str, Any] | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> OpsEventLog:
    event = OpsEventLog(
        event_id=str(uuid.uuid4()),
        module=module,
        entity_type=entity_type,
        entity_ref=str(entity_ref),
        action=action,
        status=status,
        operator=operator,
        target_connection_id=target_connection_id,
        target_database_key=target_database_key,
        target_source_code=target_source_code,
        correlation_id=correlation_id,
        batch_code=batch_code,
        affected_count=affected_count,
        duration_ms=duration_ms,
        error_code=error_code,
        summary_masked=(summary_masked or "")[:500] or None,
        detail=mask_sensitive(detail) if detail else None,
        started_at=started_at,
        finished_at=finished_at or datetime.now(timezone.utc),
    )
    db.add(event)
    return event
