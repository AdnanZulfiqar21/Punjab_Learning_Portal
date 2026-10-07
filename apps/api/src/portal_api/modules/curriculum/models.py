"""Curriculum and source domain (roadmap §5.2 Curriculum/Mapping, P05.S1).

Class XI and Class XII are separate BookEdition rows with separate stable IDs; a chapter number or subject name
alone is never an identifier. Every chapter/topic keeps its source reference (PDF page; printed pages where known).
"""

from __future__ import annotations

import uuid
from datetime import datetime
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


class Region(Base):
    __tablename__ = "region"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))


class Grade(Base):
    __tablename__ = "grade"
    __table_args__ = (UniqueConstraint("region_id", "number"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    region_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("region.id", ondelete="RESTRICT"))
    number: Mapped[int] = mapped_column(SmallInteger)
    code: Mapped[str] = mapped_column(String(8))
    name: Mapped[str] = mapped_column(String(80))


class Subject(Base):
    __tablename__ = "subject"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    display_order: Mapped[int] = mapped_column(SmallInteger)
    aliases: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # SCOPE-01: only active subjects are offered; others may exist later as inactive records.
    active: Mapped[bool] = mapped_column(default=True)


class SourceDocument(Base):
    """An owner-supplied original (P22.S1). The file itself stays outside the repository; we keep its checksum."""

    __tablename__ = "source_document"
    __table_args__ = (
        CheckConstraint(
            "publication_rights in ('UNVERIFIED','CONFIRMED','DENIED')", name="source_document_publication_rights"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(40), unique=True)
    grade_number: Mapped[int] = mapped_column(SmallInteger)
    subject_code: Mapped[str] = mapped_column(String(40))
    title: Mapped[str | None] = mapped_column(Text)
    authority: Mapped[str | None] = mapped_column(Text)
    edition: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    bytes: Mapped[int]
    pdf_pages: Mapped[int]
    page_rule: Mapped[str | None] = mapped_column(Text)
    completeness: Mapped[str] = mapped_column(String(20))
    missing_pages: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    duplicate_pages: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    rights: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    # Publication-rights gate for material derived from this source. Set only by the owner (audited, MFA); imports never
    # touch it. UNVERIFIED blocks publication of derived academic content; it does not block drafting or review.
    publication_rights: Mapped[str] = mapped_column(String(12), default="UNVERIFIED", server_default="UNVERIFIED")
    publication_rights_evidence: Mapped[str | None] = mapped_column(Text)
    publication_rights_set_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="RESTRICT", name="fk_source_document_rights_set_by")
    )
    publication_rights_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BookEdition(Base):
    __tablename__ = "book_edition"
    __table_args__ = (UniqueConstraint("grade_id", "subject_id", "source_document_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    natural_key: Mapped[str] = mapped_column(Text, unique=True)
    grade_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("grade.id", ondelete="RESTRICT"))
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subject.id", ondelete="RESTRICT"))
    source_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_document.id", ondelete="RESTRICT"))
    title: Mapped[str | None] = mapped_column(Text)
    chapter_label: Mapped[str] = mapped_column(String(20))

    grade: Mapped[Grade] = relationship(lazy="joined")
    subject: Mapped[Subject] = relationship(lazy="joined")
    source: Mapped[SourceDocument] = relationship(lazy="joined")
    chapters: Mapped[list[Chapter]] = relationship(back_populates="book", order_by="Chapter.display_order")


class Chapter(Base):
    __tablename__ = "chapter"
    __table_args__ = (
        Index(
            "uq_chapter_order_active",
            "book_id",
            "display_order",
            unique=True,
            postgresql_where=text("retired_at is null"),
        ),
        CheckConstraint("status in ('complete','partial','missing')", name="chapter_status"),
        Index("ix_chapter_title_trgm", "title", postgresql_using="gin", postgresql_ops={"title": "gin_trgm_ops"}),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    natural_key: Mapped[str] = mapped_column(Text, unique=True)
    book_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("book_edition.id", ondelete="RESTRICT"), index=True)
    display_order: Mapped[int] = mapped_column(SmallInteger)
    number: Mapped[int] = mapped_column(SmallInteger)  # as printed in the book body; display only
    contents_number: Mapped[int | None] = mapped_column(SmallInteger)  # where the Contents page differs
    title: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10))
    printed_start: Mapped[int | None] = mapped_column(Integer)
    printed_end: Mapped[int | None] = mapped_column(Integer)
    pdf_start: Mapped[int | None] = mapped_column(Integer)
    pdf_end: Mapped[int | None] = mapped_column(Integer)
    slo_codes: Mapped[str | None] = mapped_column(Text)
    main_concept: Mapped[str | None] = mapped_column(Text)
    key_terms: Mapped[list[str]] = mapped_column(JSONB, default=list)
    visual_count: Mapped[int] = mapped_column(Integer, default=0)
    assessment_counts: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    # Academic state of derived teaching material for this chapter. Source indexing is not academic approval.
    content_state: Mapped[str] = mapped_column(String(40), default="SOURCE_INDEXED")
    # Retired entities stay in place for historical references (attempts, notes, mappings) but are hidden from
    # learners (IMPL-08). They are never deleted.
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    book: Mapped[BookEdition] = relationship(back_populates="chapters")
    topics: Mapped[list[Topic]] = relationship(back_populates="chapter", order_by="Topic.display_order")


class Topic(Base):
    __tablename__ = "topic"
    __table_args__ = (
        Index(
            "uq_topic_order_active",
            "chapter_id",
            "display_order",
            unique=True,
            postgresql_where=text("retired_at is null"),
        ),
        Index("ix_topic_title_trgm", "title", postgresql_using="gin", postgresql_ops={"title": "gin_trgm_ops"}),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    natural_key: Mapped[str] = mapped_column(Text, unique=True)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapter.id", ondelete="RESTRICT"), index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topic.id", ondelete="RESTRICT"), index=True)
    display_order: Mapped[int] = mapped_column(Integer)
    number: Mapped[str | None] = mapped_column(String(20))  # printed heading number, e.g. "13.1.2"
    title: Mapped[str] = mapped_column(Text)
    depth: Mapped[int] = mapped_column(SmallInteger)
    pdf_page: Mapped[int | None] = mapped_column(Integer)
    points: Mapped[list[str]] = mapped_column(JSONB, default=list)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    chapter: Mapped[Chapter] = relationship(back_populates="topics")


class ImportBatch(Base):
    """Every imported object is traceable to a batch (roadmap §10.1 importer conventions)."""

    __tablename__ = "import_batch"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(40))
    input_sha256: Mapped[str] = mapped_column(String(64))
    dry_run: Mapped[bool]
    status: Mapped[str] = mapped_column(String(20))
    counts: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    errors: Mapped[list[str]] = mapped_column(JSONB, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
