"""Lesson completion (roadmap P07.S1.T3 and the §6.6 "content completed" meter; LESSON-DONE-01).

A learner marks a published lesson they can read as completed, and can undo it. The record pins the lesson version
read. "Content completed" for a book is completed live lessons ÷ live lessons in that book. If the book has no live
lessons, the meter is unavailable rather than an invented percentage. Completion is engagement, never evidence of
knowledge: it feeds only this meter, never `evidence_rules_v2`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base
from portal_api.errors import Forbidden, NotFound
from portal_api.modules.content.models import Availability, ContentItem


class LessonCompletion(Base):
    __tablename__ = "lesson_completion"
    __table_args__ = (UniqueConstraint("user_id", "item_id", name="uq_lesson_completion"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_item.id", ondelete="RESTRICT"))
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_version.id", ondelete="RESTRICT"))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _readable_lesson(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> ContentItem:
    from portal_api.modules.access import service as access

    item = db.get(ContentItem, item_id)
    if item is None or item.kind != "lesson" or item.availability != Availability.live.value:
        raise NotFound("Lesson not found.")
    if item.access_tier != "preview" and not access.active_entitlements(db, user_id, access.db_now(db)):
        raise Forbidden("This lesson is included with a plan or the free trial.")
    return item


def complete(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> None:
    item = _readable_lesson(db, user_id, item_id)
    existing = db.scalar(
        select(LessonCompletion).where(LessonCompletion.user_id == user_id, LessonCompletion.item_id == item.id)
    )
    if existing is None:
        assert item.published_version_id is not None
        db.add(LessonCompletion(user_id=user_id, item_id=item.id, version_id=item.published_version_id))
        from portal_api.modules.analytics.events import emit

        emit(
            db,
            "lesson.completed",
            key=f"{user_id}:{item.id}:{item.published_version_id}",
            user_id=user_id,
            lesson_id=str(item.id),
            version_id=str(item.published_version_id),
        )
        db.commit()


def undo(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> None:
    row = db.scalar(
        select(LessonCompletion).where(LessonCompletion.user_id == user_id, LessonCompletion.item_id == item_id)
    )
    if row is not None:
        db.delete(row)
        db.commit()


def completed_in(db: Session, user_id: uuid.UUID, chapter_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not chapter_ids:
        return set()
    return set(
        db.scalars(
            select(LessonCompletion.item_id)
            .join(ContentItem, ContentItem.id == LessonCompletion.item_id)
            .where(LessonCompletion.user_id == user_id, ContentItem.chapter_id.in_(chapter_ids))
        )
    )


def meter(db: Session, user_id: uuid.UUID, chapter_ids: list[uuid.UUID]) -> float | None:
    live = (
        set(
            db.scalars(
                select(ContentItem.id).where(
                    ContentItem.kind == "lesson",
                    ContentItem.availability == Availability.live.value,
                    ContentItem.chapter_id.in_(chapter_ids),
                )
            )
        )
        if chapter_ids
        else set()
    )
    if not live:
        return None
    done = completed_in(db, user_id, chapter_ids) & live
    return round(100 * len(done) / len(live), 1)
