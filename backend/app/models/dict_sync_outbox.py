"""Dictionary sync outbox events (112 A5).

Persistent task queue for cross-system dictionary writes. Replaces the
"call write directly on approval" path with a durable, at-least-once
event that can be replayed after restart.

Rules from plan 112 A2/A5:
- Approving a plan creates one outbox event per target system (not per row).
- The worker leases the event (FOR UPDATE SKIP LOCKED), executes the whole
  per-target transaction, and commits. Lease expiry allows restart recovery.
- Attempts are bounded (max_attempts), then the event becomes dead_letter.
- All rows live in asset schema with asset_ prefix.
"""

from sqlalchemy import BigInteger, Column, Integer, Text, TIMESTAMP, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..core.db import Base


class DictSyncOutboxEvent(Base):
    """One durable outbox event referencing a per-target dispatch task."""
    __tablename__ = "asset_dict_sync_outbox"
    __table_args__ = (
        UniqueConstraint("business_key"),
        {"schema": "asset"},
    )

    id = Column(BigInteger, primary_key=True)
    # Stable dedup key: e.g. "plan:12:HIS" or "batch:VALB-xxxx:CDMS"
    business_key = Column(Text, nullable=False)
    category = Column(Text, nullable=False)  # dict_push | identity_batch
    target_system = Column(Text, nullable=False)  # HIS | JHEMR_VASTBASE | CDMS | JHEMR
    event_type = Column(Text, nullable=False)  # plan_approve | identity_batch
    plan_id = Column(BigInteger)
    plan_hash = Column(Text)  # plan.content_hash recorded at enqueue time
    batch_id = Column(Text)
    payload = Column(JSONB)

    # State machine
    status = Column(Text, server_default="pending")
    # pending | leased | succeeded | failed | dead_letter
    attempt = Column(Integer, server_default="0")
    max_attempts = Column(Integer, server_default="3")
    next_retry_at = Column(TIMESTAMP(timezone=True))
    lease_expires_at = Column(TIMESTAMP(timezone=True))
    lease_holder = Column(Text)
    last_error_masked = Column(Text)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "business_key": self.business_key,
            "category": self.category,
            "target_system": self.target_system,
            "event_type": self.event_type,
            "plan_id": self.plan_id,
            "plan_hash": self.plan_hash,
            "batch_id": self.batch_id,
            "status": self.status,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "lease_expires_at": self.lease_expires_at.isoformat() if self.lease_expires_at else None,
            "lease_holder": self.lease_holder,
            "last_error_masked": self.last_error_masked,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
