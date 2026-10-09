"""Practice forms, attempts and the durable answer ledger (roadmap P09.S3.T3, P10, §10.5).

A form is frozen before the first answer: question versions, display order, option permutations (stable option IDs),
marks, timing, tolerance and the scoring policy. An attempt pins that form. Every client save operation is recorded
once in `answer_op` with its disposition; the current answer per position lives in `attempt_answer`. Finalisation
writes exactly one `submission_receipt`; scoring writes immutable `score_version` rows.
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
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from portal_api.db import Base

SCORING_POLICY_VERSION = 1


class PracticeForm(Base):
    __tablename__ = "practice_form"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_practice_form_idempotency"),
        CheckConstraint("feedback_mode in ('deferred','immediate')", name="practice_form_feedback_mode"),
        CheckConstraint("invalid_item_treatment in ('EXCLUDE','CREDIT_ALL')", name="practice_form_invalid_item"),
        CheckConstraint("question_count between 1 and 200", name="practice_form_count"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(64))  # same key + different request is a conflict
    kind: Mapped[str] = mapped_column(String(20), default="practice")
    grade_number: Mapped[int] = mapped_column(SmallInteger)
    subject_code: Mapped[str] = mapped_column(String(40))
    scope: Mapped[dict[str, Any]] = mapped_column(JSONB)  # {"chapter_ids": [...], "topic_ids": [...]}
    seed: Mapped[int] = mapped_column(BigInteger)  # auditable randomness: the form is reproducible from its inputs
    question_count: Mapped[int] = mapped_column(SmallInteger)
    duration_s: Mapped[int | None] = mapped_column(Integer)  # None = untimed
    late_write_tolerance_ms: Mapped[int] = mapped_column(Integer)
    feedback_mode: Mapped[str] = mapped_column(String(12))
    negative_marks: Mapped[int] = mapped_column(SmallInteger, default=0)
    invalid_item_treatment: Mapped[str] = mapped_column(String(12), default="EXCLUDE")
    scoring_policy_version: Mapped[int] = mapped_column(SmallInteger, default=SCORING_POLICY_VERSION)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list[FormItem]] = relationship(back_populates="form", order_by="FormItem.position")


class FormItem(Base):
    __tablename__ = "form_item"
    __table_args__ = (
        UniqueConstraint("form_id", "position"),
        UniqueConstraint("form_id", "family_id", name="uq_form_item_family"),  # no sibling variants in one form
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("practice_form.id", ondelete="RESTRICT"), index=True)
    position: Mapped[int] = mapped_column(SmallInteger)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_item.id", ondelete="RESTRICT"))
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_version.id", ondelete="RESTRICT"))
    marks: Mapped[int] = mapped_column(SmallInteger)
    option_order: Mapped[list[str]] = mapped_column(JSONB)  # frozen permutation of stable option IDs
    # OCT9-03: the question's class and subject, frozen with the form, so reports never move between buckets later.
    grade_number: Mapped[int] = mapped_column(SmallInteger)
    subject_code: Mapped[str] = mapped_column(String(40))

    form: Mapped[PracticeForm] = relationship(back_populates="items")


class Attempt(Base):
    __tablename__ = "attempt"
    __table_args__ = (
        UniqueConstraint("form_id", "user_id", name="uq_attempt_form_user"),
        CheckConstraint("status in ('active','finalised','void')", name="attempt_status"),
        CheckConstraint("finalise_reason is null or finalise_reason in ('manual','expiry')", name="attempt_reason"),
        Index("ix_attempt_active_cutoff", "cutoff_at", postgresql_where=text("status = 'active'")),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("practice_form.id", ondelete="RESTRICT"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # D: published editing deadline; T: pinned late-write tolerance; C = D + T: server admission cutoff (§10.5).
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tolerance_ms: Mapped[int] = mapped_column(Integer)
    cutoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalise_reason: Mapped[str | None] = mapped_column(String(10))
    # OCT9-01/02: when the mistake notebook last reflected this attempt (None: not yet, e.g. results still held).
    notebook_applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    form: Mapped[PracticeForm] = relationship()


class AnswerOp(Base):
    """Every save operation the server admitted, with its disposition. Exact replays return this original receipt."""

    __tablename__ = "answer_op"
    __table_args__ = (
        UniqueConstraint("attempt_id", "op_id", name="uq_answer_op"),
        CheckConstraint(
            "disposition in ('accepted','stale','invalid','late','finalised','locked')", name="answer_op_disposition"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempt.id", ondelete="RESTRICT"), index=True)
    op_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    payload_hash: Mapped[str] = mapped_column(String(64))
    position: Mapped[int] = mapped_column(SmallInteger)
    revision: Mapped[int] = mapped_column(Integer)
    option_id: Mapped[str | None] = mapped_column(String(12))
    admitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    disposition: Mapped[str] = mapped_column(String(12))
    via: Mapped[str] = mapped_column(String(10))  # "save" or "submit"


class AttemptAnswer(Base):
    """The committed current answer per position (latest accepted revision)."""

    __tablename__ = "attempt_answer"
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempt.id", ondelete="RESTRICT"), primary_key=True)
    position: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    option_id: Mapped[str | None] = mapped_column(String(12))
    revision: Mapped[int] = mapped_column(Integer)
    op_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # immediate feedback locks the item


class SubmissionReceipt(Base):
    """One logical receipt per attempt. Never rewritten to pretend it saw later work."""

    __tablename__ = "submission_receipt"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempt.id", ondelete="RESTRICT"), unique=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(80))  # None for automatic expiry
    reason: Mapped[str] = mapped_column(String(10))
    admitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    answered_count: Mapped[int] = mapped_column(SmallInteger)
    question_count: Mapped[int] = mapped_column(SmallInteger)
    ledger_hash: Mapped[str] = mapped_column(String(64))  # sha256 of the frozen final-answer ledger
    included_ops: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScoreVersion(Base):
    __tablename__ = "score_version"
    __table_args__ = (
        UniqueConstraint("attempt_id", "version"),
        UniqueConstraint("attempt_id", "scoring_policy_version", "adjudication_hash", name="uq_score_effective_inputs"),
        CheckConstraint("status in ('scored','not_scorable')", name="score_version_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempt.id", ondelete="RESTRICT"), index=True)
    version: Mapped[int] = mapped_column(SmallInteger)
    scoring_policy_version: Mapped[int] = mapped_column(SmallInteger)
    adjudication_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(14))
    raw: Mapped[int] = mapped_column(Integer)
    maximum: Mapped[int] = mapped_column(Integer)
    percentage: Mapped[float | None] = mapped_column(Numeric(6, 2))
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class McqAdjudication(Base):
    """A reviewed score correction for one exact MCQ version (§5.7): VOID (pinned invalid-item treatment) or KEY_ERROR
    (KEY_CORRECTION with the reviewed key). Never edits the question or any attempt; superseded explicitly."""

    __tablename__ = "mcq_adjudication"
    __table_args__ = (
        CheckConstraint("defect in ('VOID','KEY_ERROR')", name="mcq_adjudication_defect"),
        CheckConstraint("status in ('effective','superseded')", name="mcq_adjudication_status"),
        CheckConstraint(
            "(defect = 'KEY_ERROR') = (corrected_option_id is not null)", name="mcq_adjudication_corrected_key"
        ),
        Index(
            "uq_mcq_adjudication_effective",
            "version_id",
            unique=True,
            postgresql_where=text("status = 'effective'"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_item.id", ondelete="RESTRICT"), index=True)
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_version.id", ondelete="RESTRICT"), index=True)
    defect: Mapped[str] = mapped_column(String(10))
    corrected_option_id: Mapped[str | None] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(Text)
    decided_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(12), default="effective")
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mcq_adjudication.id", ondelete="RESTRICT"))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
