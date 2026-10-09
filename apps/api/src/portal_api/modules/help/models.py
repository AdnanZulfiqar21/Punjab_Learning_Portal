from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from portal_api.db import Base


class HelpArticle(Base):
    """One help topic in one language. Readers see only its published version; staff edit a working version."""

    __tablename__ = "help_article"
    __table_args__ = (
        UniqueConstraint("slug", "locale", name="uq_help_article_slug_locale"),
        CheckConstraint("locale in ('en','ur')", name="help_article_locale"),
        CheckConstraint("status in ('draft','published','retired')", name="help_article_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80))
    locale: Mapped[str] = mapped_column(String(2), default="en")
    status: Mapped[str] = mapped_column(String(10), default="draft")
    working_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("help_article_version.id", ondelete="RESTRICT", use_alter=True, name="fk_help_working")
    )
    published_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("help_article_version.id", ondelete="RESTRICT", use_alter=True, name="fk_help_published")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HelpArticleVersion(Base):
    """An immutable text of an article. Published versions are never edited; a change makes a new version."""

    __tablename__ = "help_article_version"
    __table_args__ = (UniqueConstraint("article_id", "number", name="uq_help_version_number"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("help_article.id", ondelete="RESTRICT"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(160))
    summary: Mapped[str] = mapped_column(String(400))
    body: Mapped[dict[str, Any]] = mapped_column(JSONB)  # content blocks (heading, paragraph, list, callout)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    search_text: Mapped[str] = mapped_column(Text)
    source_hash: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))


class ServiceIncident(Base):
    """A known outage or degradation shown to everyone (P15.S2.T3). Its updates form a public timeline."""

    __tablename__ = "service_incident"
    __table_args__ = (
        CheckConstraint(
            "status in ('investigating','identified','monitoring','resolved')", name="service_incident_status"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(14), default="investigating")
    components: Mapped[list[str]] = mapped_column(JSONB, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))


class ServiceIncidentUpdate(Base):
    __tablename__ = "service_incident_update"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_incident.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(14))
    message: Mapped[str] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
