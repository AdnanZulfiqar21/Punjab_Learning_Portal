"""Editorial content domain (roadmap §5.2 Teaching, P06.S1/P06.S3).

A ContentItem is a stable identity (e.g. one lesson for a chapter or topic). Its text lives in immutable-once-submitted
ContentVersions. Only one version per item is the *working* version (editable while draft/changes requested), and at
most one is *published*. Approving is an independent academic decision by someone who did not edit that version;
publishing is a separate MFA-protected step. Nothing is ever deleted: items are retired, versions superseded.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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
from portal_api.observability import current_correlation


class ItemState(StrEnum):
    """Editorial state of the item's working version, shown in the work queue (P06.S1.T2). `published` means the
    working version is the live one (no revision in progress)."""

    draft = "draft"
    submitted = "submitted"
    changes_requested = "changes_requested"
    approved = "approved"
    published = "published"


class Availability(StrEnum):
    """What learners can see, independent of editorial work on a newer version (§5.7)."""

    unpublished = "unpublished"
    live = "live"
    quarantined = "quarantined"  # hidden from learners while a suspected defect is investigated
    retired = "retired"  # hidden permanently; kept for history, never deleted


class VersionStatus(StrEnum):
    draft = "draft"
    submitted = "submitted"
    changes_requested = "changes_requested"
    approved = "approved"
    published = "published"
    superseded = "superseded"  # an older published version, or a draft abandoned by retirement


ITEM_KINDS = ("lesson", "mcq", "written", "rubric", "storyboard", "passage")  # see kinds.py
QUARANTINE_LEVELS = ("SOFT", "VOID", "KEY_ERROR")  # §5.7, questions only


class ContentItem(Base):
    __tablename__ = "content_item"
    __table_args__ = (
        CheckConstraint(f"state in ({', '.join(repr(s.value) for s in ItemState)})", name="content_item_state"),
        CheckConstraint(
            f"availability in ({', '.join(repr(s.value) for s in Availability)})", name="content_item_availability"
        ),
        CheckConstraint(f"kind in ({', '.join(repr(k) for k in ITEM_KINDS)})", name="content_item_kind"),
        CheckConstraint(
            "availability not in ('live','quarantined') or published_version_id is not null",
            name="content_item_live_has_version",
        ),
        CheckConstraint(
            f"quarantine_level is null or quarantine_level in ({', '.join(repr(q) for q in QUARANTINE_LEVELS)})",
            name="content_item_quarantine_level",
        ),
        Index(
            "uq_content_item_external_ref",
            "kind",
            "external_ref",
            unique=True,
            postgresql_where=text("external_ref is not null"),
        ),
        Index("ix_content_item_queue", "state", "grade_number", "subject_code"),
        Index("ix_content_item_live", "chapter_id", postgresql_where=text("availability = 'live'")),
        CheckConstraint("access_tier in ('preview','premium')", name="content_item_access_tier"),
        CheckConstraint("question_pool in ('practice','mock')", name="content_item_question_pool"),
        CheckConstraint("language in ('en','ur','roman_ur')", name="content_item_language"),
        CheckConstraint(
            "translation_origin is null or translation_origin in ('human','machine_draft')",
            name="content_item_translation_origin",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(20))
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapter.id", ondelete="RESTRICT"), index=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topic.id", ondelete="RESTRICT"), index=True)
    # Denormalised from the chapter's book for scope checks and queue filters; a chapter never changes book.
    grade_number: Mapped[int] = mapped_column(SmallInteger)
    subject_code: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(24), default=ItemState.draft.value)
    availability: Mapped[str] = mapped_column(String(16), default=Availability.unpublished.value)
    # Review R07: lessons are premium (needs an active plan or trial) unless a publisher explicitly marks a free
    # preview, with a recorded reason. Which lessons are previews is a product decision (ACCESS-02).
    access_tier: Mapped[str] = mapped_column(String(10), default="premium", server_default="premium")
    # P08.S3.T3: questions reserved for mocks never appear in practice tests (publisher decision, audited).
    question_pool: Mapped[str] = mapped_column(String(10), default="practice", server_default="practice")
    # P07.S1.T2 (LESSON-VARIANTS-01): one lesson concept, several languages, each its own item with its own review.
    language: Mapped[str] = mapped_column(String(10), default="en", server_default="en")
    concept_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)  # None: its own concept
    translation_origin: Mapped[str | None] = mapped_column(String(14))  # variants: human | machine_draft
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    assigned_reviewer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    working_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("content_version.id", ondelete="RESTRICT", use_alter=True, name="fk_item_working_version")
    )
    published_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("content_version.id", ondelete="RESTRICT", use_alter=True, name="fk_item_published_version")
    )
    availability_reason: Mapped[str | None] = mapped_column(Text)  # quarantine/retirement reason
    quarantine_level: Mapped[str | None] = mapped_column(String(12))  # SOFT / VOID / KEY_ERROR for questions (§5.7)
    # P06.S2 (IMPORT-01): the author's stable row ID for imported items (unique per kind) and the hash of the last
    # imported payload, so re-importing an unchanged file writes nothing.
    external_ref: Mapped[str | None] = mapped_column(String(120))
    import_hash: Mapped[str | None] = mapped_column(String(64))
    # Canonical question family (P08.S3.T1): reviewed variants/translations share one family, so sampling and exposure
    # caps treat them as one underlying item. Null for lessons.
    family_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    # A rubric belongs to one written question (§20.6.2); other kinds have no parent.
    parent_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("content_item.id", ondelete="RESTRICT", name="fk_content_item_parent"), index=True
    )

    versions: Mapped[list[ContentVersion]] = relationship(
        back_populates="item", foreign_keys="ContentVersion.item_id", order_by="ContentVersion.number"
    )
    working: Mapped[ContentVersion | None] = relationship(foreign_keys=[working_version_id], post_update=True)
    published: Mapped[ContentVersion | None] = relationship(foreign_keys=[published_version_id], post_update=True)


class ContentVersion(Base):
    __tablename__ = "content_version"
    __table_args__ = (
        Index("uq_content_version_number", "item_id", "number", unique=True),
        Index(
            "uq_content_version_one_published",
            "item_id",
            unique=True,
            postgresql_where=text("status = 'published'"),
        ),
        # SEARCH-01: full-text index over the searchable lesson text; `lesson_search_text` is defined in migration
        # f6a1c3e8b204 (see content.search).
        Index(
            "ix_content_version_search",
            text("to_tsvector('english'::regconfig, lesson_search_text(body))"),
            postgresql_using="gin",
        ),
        CheckConstraint(
            f"status in ({', '.join(repr(s.value) for s in VersionStatus)})", name="content_version_status"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_item.id", ondelete="RESTRICT"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default=VersionStatus.draft.value)
    # Optimistic concurrency for autosave (P06.S1.T3): every save must name the revision it started from.
    revision: Mapped[int] = mapped_column(Integer, default=1)
    content_schema_version: Mapped[int] = mapped_column(SmallInteger)
    body: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    block_types: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # [{source_document_id, pdf_from, pdf_to, note}] — every academic item links to its source pages.
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    change_reason: Mapped[str | None] = mapped_column(Text)  # required for every version after the first
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    # Everyone who changed this version's text. None of them may approve or publish it (independent review).
    contributors: Mapped[list[str]] = mapped_column(JSONB, default=list)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    item: Mapped[ContentItem] = relationship(back_populates="versions", foreign_keys=[item_id])
    reviews: Mapped[list[ReviewDecision]] = relationship(back_populates="version", order_by="ReviewDecision.created_at")


class ReviewDecision(Base):
    """An academic reviewer's decision on one submitted version. Append-only."""

    __tablename__ = "review_decision"
    __table_args__ = (CheckConstraint("decision in ('approve','request_changes')", name="review_decision_decision"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_version.id", ondelete="RESTRICT"), index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    decision: Mapped[str] = mapped_column(String(20))
    comment: Mapped[str] = mapped_column(Text)
    # Checks the reviewer confirmed (e.g. accuracy, ambiguity, units, diagrams, grammar, mapping for questions).
    checklist: Mapped[dict[str, bool]] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    version: Mapped[ContentVersion] = relationship(back_populates="reviews")


class ContentImportBatch(Base):
    """A structured import (P06.S2, IMPORT-01): previewed (dry run), then committed atomically, or discarded."""

    __tablename__ = "content_import_batch"
    __table_args__ = (
        CheckConstraint(
            "status in ('queued','validating','previewed','committing','committed','discarded','failed')",
            name="content_import_batch_status",
        ),
        CheckConstraint("format in ('json','csv','xlsx')", name="content_import_batch_format"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(20))
    format: Mapped[str] = mapped_column(String(8))
    filename: Mapped[str] = mapped_column(String(200))
    sha256: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(String(12), default="previewed")
    counts: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # IMPORT-BULK-01: large files are checked and committed by the import worker.
    rows_total: Mapped[int | None] = mapped_column(Integer)
    rows_checked: Mapped[int | None] = mapped_column(Integer)
    file_key: Mapped[str | None] = mapped_column(Text)  # the private upload, deleted once its rows are stored
    failure: Mapped[str | None] = mapped_column(Text)
    lease_owner: Mapped[str | None] = mapped_column(String(120))  # the current claim's token (OCT14-02)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # claims in this phase (OCT14-03)
    last_error: Mapped[str | None] = mapped_column(Text)  # the last unexpected error, for operators only
    # CORRELATION-01: the correlation ID of the request that created this row (None: created outside a request).
    correlation_id: Mapped[str | None] = mapped_column(String(64), default=current_correlation)


class ContentImportRow(Base):
    __tablename__ = "content_import_row"
    __table_args__ = (
        UniqueConstraint("batch_id", "row_number", name="uq_content_import_row"),
        CheckConstraint("action in ('create','update','unchanged','skip','error')", name="content_import_row_action"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_import_batch.id", ondelete="CASCADE"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    external_id: Mapped[str | None] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(10))
    errors: Mapped[list[str]] = mapped_column(JSONB, default=list)
    warnings: Mapped[list[str]] = mapped_column(JSONB, default=list)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    payload_hash: Mapped[str | None] = mapped_column(String(64))
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("content_item.id", ondelete="RESTRICT"))


class ContentRelease(Base):
    """RELEASE-01 (P06.S3.T2): several approved items published together in one transaction, or none of them.

    A release can be rolled back as a whole: each item goes back to the version it had before (or off learners'
    screens if the release first published it). Nothing is deleted; the entries say what changed."""

    __tablename__ = "content_release"
    __table_args__ = (CheckConstraint("status in ('published','rolled_back')", name="content_release_status"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="published")
    published_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rolled_back_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rollback_reason: Mapped[str | None] = mapped_column(Text)

    entries: Mapped[list[ContentReleaseEntry]] = relationship(order_by="ContentReleaseEntry.position")


class ContentReleaseEntry(Base):
    """One item of a release: the version it published and the version learners saw before (none if the release first
    published the item)."""

    __tablename__ = "content_release_entry"
    __table_args__ = (UniqueConstraint("release_id", "item_id", name="uq_content_release_entry_item"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    release_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_release.id", ondelete="RESTRICT"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_item.id", ondelete="RESTRICT"), index=True)
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_version.id", ondelete="RESTRICT"))
    previous_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("content_version.id", ondelete="RESTRICT"))
    position: Mapped[int] = mapped_column(SmallInteger)
