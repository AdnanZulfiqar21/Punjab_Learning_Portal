"""Support tickets and academic error reports (P15.S3).

A ticket belongs to one learner. It may reference the learner's own attempt (and, for academic reports, the exact
question version the server resolved from that attempt). Staff messages can be internal notes that learners never see.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from portal_api.db import Base

CATEGORIES = ("account", "access", "technical", "academic_report", "other")
STATUSES = ("open", "in_progress", "waiting_learner", "resolved")


class SupportTicket(Base):
    __tablename__ = "support_ticket"
    __table_args__ = (
        CheckConstraint(f"category in ({', '.join(repr(c) for c in CATEGORIES)})", name="support_ticket_category"),
        CheckConstraint(f"status in ({', '.join(repr(s) for s in STATUSES)})", name="support_ticket_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    category: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="open")
    # The learner's own reference, validated on creation: {"kind": "attempt"|"written_attempt", "id": …, "position": n}
    reference: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Academic reports: resolved server-side so they route to the right reviewers with exact versions.
    content_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("content_item.id", ondelete="RESTRICT"))
    content_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("content_version.id", ondelete="RESTRICT"))
    grade_number: Mapped[int | None] = mapped_column(SmallInteger)
    subject_code: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SupportMessage(Base):
    __tablename__ = "support_message"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("support_ticket.id", ondelete="RESTRICT"), index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    from_staff: Mapped[bool] = mapped_column(default=False)
    internal: Mapped[bool] = mapped_column(default=False)  # staff-only note; never shown to the learner
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
