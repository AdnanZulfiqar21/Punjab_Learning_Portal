"""Written practice forms, attempts, evidence pages, answer mapping and sealed receipts (W03/W04, §20.7).

Timing: writing deadline D, disclosed upload allowance G, final upload/seal cutoff U = D + G, all from server time and
pinned at start. Untimed practice has no D but still a finite upload permit (U). Pages are immutable objects; the
manifest maps scorable slots (question position + subpart) to pages, or records an explicit unanswered declaration,
under a revision number. Sealing writes exactly one receipt; nothing is assessed before it.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from portal_api.db import Base

CAPTURE_POLICY_VERSION = 1


class WrittenForm(Base):
    __tablename__ = "written_form"
    __table_args__ = (UniqueConstraint("owner_id", "idempotency_key", name="uq_written_form_idempotency"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(64))
    grade_number: Mapped[int] = mapped_column(SmallInteger)
    subject_code: Mapped[str] = mapped_column(String(40))
    scope: Mapped[dict[str, Any]] = mapped_column(JSONB)
    seed: Mapped[int] = mapped_column(BigInteger)
    question_type: Mapped[str] = mapped_column(String(10))  # short | long | mixed
    writing_s: Mapped[int | None] = mapped_column(Integer)  # None = untimed
    upload_allowance_s: Mapped[int] = mapped_column(Integer)  # G (timed) or the untimed upload permit
    capture_policy_version: Mapped[int] = mapped_column(SmallInteger, default=CAPTURE_POLICY_VERSION)
    caps: Mapped[dict[str, int]] = mapped_column(JSONB)  # max pages, aggregate bytes, per-file bytes
    max_units: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list[WrittenFormItem]] = relationship(back_populates="form", order_by="WrittenFormItem.position")


class WrittenFormItem(Base):
    __tablename__ = "written_form_item"
    __table_args__ = (UniqueConstraint("form_id", "position"), UniqueConstraint("form_id", "family_id"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_form.id", ondelete="RESTRICT"), index=True)
    position: Mapped[int] = mapped_column(SmallInteger)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_item.id", ondelete="RESTRICT"))
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    question_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_version.id", ondelete="RESTRICT"))
    rubric_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_version.id", ondelete="RESTRICT"))
    max_units: Mapped[int] = mapped_column(Integer)
    slots: Mapped[list[str]] = mapped_column(JSONB)  # slot keys "<position>:<subpart|*>"

    form: Mapped[WrittenForm] = relationship(back_populates="items")


class WrittenAttempt(Base):
    __tablename__ = "written_attempt"
    __table_args__ = (
        UniqueConstraint("form_id", "user_id", name="uq_written_attempt_form_user"),
        CheckConstraint("status in ('active','sealed','expired')", name="written_attempt_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_form.id", ondelete="RESTRICT"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(10), default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    writing_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # D
    upload_allowance_s: Mapped[int] = mapped_column(Integer)  # G, pinned
    upload_cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # U
    sealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Mapping manifest: {"slots": {slot: {"pages": [page_id...], "unanswered": bool}}, "order": [page_id...]}
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    manifest_revision: Mapped[int] = mapped_column(Integer, default=0)

    form: Mapped[WrittenForm] = relationship()


class WrittenPage(Base):
    """An uploaded evidence object: immutable, never overwritten. Exact duplicates are reused within one attempt."""

    __tablename__ = "written_page"
    __table_args__ = (
        UniqueConstraint("attempt_id", "sha256", name="uq_written_page_attempt_hash"),
        CheckConstraint("status in ('uploaded','withdrawn')", name="written_page_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_attempt.id", ondelete="RESTRICT"), index=True)
    storage_key: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    content_type: Mapped[str] = mapped_column(String(40))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    pdf_pages: Mapped[int] = mapped_column(SmallInteger, default=1)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    after_cutoff: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(10), default="uploaded")


class WrittenReceipt(Base):
    """The one seal receipt. Its manifest snapshot and page hashes are what review and scoring use."""

    __tablename__ = "written_receipt"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_attempt.id", ondelete="RESTRICT"), unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(64))
    admitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    manifest_revision: Mapped[int] = mapped_column(Integer)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB)
    page_hashes: Mapped[dict[str, str]] = mapped_column(JSONB)  # page id -> sha256 verified at seal
    answered_slots: Mapped[int] = mapped_column(SmallInteger)
    unanswered_slots: Mapped[int] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
