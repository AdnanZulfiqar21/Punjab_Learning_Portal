"""Academic updates (roadmap P16.S3.T3; ACADEMIC-UPDATES-01).

* **Source review dates:** a subject reviewer in scope records that an official source was checked, with a note.
  Sources never reviewed, or not reviewed for `STALE_AFTER`, are flagged stale in the registry.
* **Syllabus notices:** any content staff member logs an official notice (a syllabus change, a board circular, an
  exam-pattern announcement) with its link and summary. It waits for a subject reviewer in that class and subject to
  decide whether it is accepted (action needed) or dismissed. A notice never changes content, profiles or rules by
  itself; every resulting change still goes through drafting, review and publication.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, String, Text, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base
from portal_api.errors import Conflict, Forbidden, NotFound
from portal_api.modules.audit.models import record
from portal_api.modules.content import workflow
from portal_api.modules.content.models import ContentItem
from portal_api.modules.curriculum.models import SourceDocument
from portal_api.modules.identity.deps import Principal
from portal_api.modules.identity.permissions import Permission, permissions_for

STALE_AFTER = timedelta(days=365)


class SourceReview(Base):
    __tablename__ = "source_review"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_document.id", ondelete="RESTRICT"), index=True
    )
    reviewed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    note: Mapped[str] = mapped_column(Text)


class SyllabusNotice(Base):
    __tablename__ = "syllabus_notice"
    __table_args__ = (
        CheckConstraint("status in ('open','accepted','dismissed')", name="syllabus_notice_status"),
        CheckConstraint("grade_number in (11, 12)", name="syllabus_notice_grade"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grade_number: Mapped[int] = mapped_column(SmallInteger)
    subject_code: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="open")
    logged_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decision: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def _perms(db: Session, who: Principal, grade: int, subject: str) -> frozenset[Permission]:
    return permissions_for(workflow.roles_in_scope(db, who.user.id, grade, subject))


def review_source(db: Session, who: Principal, source_id: uuid.UUID, note: str) -> SourceReview:
    doc = db.get(SourceDocument, source_id)
    if doc is None:
        raise NotFound("Source not found.")
    if Permission.review_content not in _perms(db, who, doc.grade_number, doc.subject_code):
        raise Forbidden("Only a subject reviewer for this class and subject can record a source review.")
    row = SourceReview(id=uuid.uuid4(), source_document_id=doc.id, reviewed_by=who.user.id, note=note.strip())
    db.add(row)
    record(
        db,
        actor=who.user.id,
        action="source.reviewed",
        target_type="source_document",
        target_id=str(doc.id),
        details={"source_id": doc.source_id, "note": note.strip()},
    )
    db.commit()
    db.refresh(row)
    return row


def last_reviews(db: Session) -> dict[uuid.UUID, datetime]:
    return dict(
        db.execute(
            select(SourceReview.source_document_id, func.max(SourceReview.reviewed_at)).group_by(
                SourceReview.source_document_id
            )
        ).all()
    )


def is_stale(last: datetime | None, now: datetime) -> bool:
    return last is None or now - last > STALE_AFTER


def log_notice(
    db: Session, who: Principal, *, grade: int, subject: str, title: str, source_url: str | None, summary: str
) -> SyllabusNotice:
    if not _perms(db, who, grade, subject) & {
        Permission.draft_content,
        Permission.review_content,
        Permission.publish_content,
    }:
        raise Forbidden("This class and subject are outside your role's scope.")
    n = SyllabusNotice(
        id=uuid.uuid4(),
        grade_number=grade,
        subject_code=subject,
        title=title.strip(),
        source_url=(source_url or "").strip() or None,
        summary=summary.strip(),
        logged_by=who.user.id,
    )
    db.add(n)
    record(
        db,
        actor=who.user.id,
        action="syllabus.notice_logged",
        target_type="syllabus_notice",
        target_id=str(n.id),
        details={"grade": grade, "subject": subject, "title": n.title},
    )
    db.commit()
    db.refresh(n)
    return n


def decide_notice(db: Session, who: Principal, notice_id: uuid.UUID, accept: bool, decision: str) -> SyllabusNotice:
    n = db.scalar(select(SyllabusNotice).where(SyllabusNotice.id == notice_id).with_for_update())
    if n is None:
        raise NotFound("Notice not found.")
    if Permission.review_content not in _perms(db, who, n.grade_number, n.subject_code):
        raise Forbidden("Only a subject reviewer for this class and subject can decide a notice.")
    if n.status != "open":
        raise Conflict(f"This notice is already {n.status}.")
    n.status = "accepted" if accept else "dismissed"
    n.decision = decision.strip()
    n.decided_by = who.user.id
    n.decided_at = func.now()
    record(
        db,
        actor=who.user.id,
        action=f"syllabus.notice_{n.status}",
        target_type="syllabus_notice",
        target_id=str(n.id),
        details={"decision": n.decision},
    )
    db.commit()
    db.refresh(n)
    return n


def notices(db: Session, who: Principal) -> list[dict[str, Any]]:
    out = []
    for n in db.scalars(select(SyllabusNotice).order_by(SyllabusNotice.logged_at.desc()).limit(200)):
        perms = _perms(db, who, n.grade_number, n.subject_code)
        if not perms & {Permission.draft_content, Permission.review_content, Permission.publish_content}:
            continue
        affected = db.scalar(
            select(func.count())
            .select_from(ContentItem)
            .where(
                ContentItem.grade_number == n.grade_number,
                ContentItem.subject_code == n.subject_code,
                ContentItem.availability == "live",
            )
        )
        out.append(
            {
                "id": n.id,
                "grade": n.grade_number,
                "subject": n.subject_code,
                "title": n.title,
                "source_url": n.source_url,
                "summary": n.summary,
                "status": n.status,
                "logged_at": n.logged_at,
                "decision": n.decision,
                "decided_at": n.decided_at,
                "live_items_in_scope": int(affected or 0),
                "can_decide": Permission.review_content in perms and n.status == "open",
            }
        )
    return out
