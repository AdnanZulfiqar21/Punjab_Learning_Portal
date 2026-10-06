"""Append-only audit trail for sensitive actions (role grants, publication, quarantine, refunds…). Roadmap §4."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base


class AuditEvent(Base):
    __tablename__ = "audit_event"
    __table_args__ = (Index("ix_audit_event_target", "target_type", "target_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    action: Mapped[str] = mapped_column(String(80))
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    correlation_id: Mapped[str | None] = mapped_column(String(64))


def record(
    session: Session,
    *,
    actor: uuid.UUID | None,
    action: str,
    target_type: str,
    target_id: str,
    details: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> AuditEvent:
    """Add an audit event to the caller's transaction, so it commits or rolls back with the audited change."""
    event = AuditEvent(
        actor_user_id=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details or {},
        correlation_id=correlation_id,
    )
    session.add(event)
    return event
