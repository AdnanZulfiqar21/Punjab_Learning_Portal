"""Lesson progress across devices that never moves backwards (P11.S2.T1; LESSON-PROGRESS-01).

* **Event order:** a completion or its undo can arrive late. The mobile app queues them offline and replays them later
  (OFFLINE-SYNC-01). Each event carries when the learner acted (`client_at`; an immediate action is "now"). A
  per-lesson clock keeps the newest accepted time, and an older event is ignored, so a stale undo never removes a
  newer completion made on another device (and a stale completion never reverses a newer undo).
* **Reading position:** where the learner last was in a chapter (lesson and block), saved from any device and moved
  only by a newer event, so "continue reading" never jumps back to an older place.

Times from devices are trusted only for ordering, and a time in the future counts as now. Nothing here is evidence of
knowledge: it feeds only "content completed" and "continue reading".
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, SmallInteger, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base
from portal_api.errors import NotFound, Unprocessable


class LessonEventClock(Base):
    __tablename__ = "lesson_event_clock"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), primary_key=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_item.id", ondelete="RESTRICT"), primary_key=True)
    client_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReadingPosition(Base):
    __tablename__ = "reading_position"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), primary_key=True)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapter.id", ondelete="RESTRICT"), primary_key=True)
    lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_item.id", ondelete="RESTRICT"))
    block_index: Mapped[int] = mapped_column(SmallInteger, default=0)
    client_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def _when(db: Session, client_at: datetime | None) -> datetime:
    now: datetime = db.execute(select(func.clock_timestamp())).scalar_one()
    if client_at is not None and client_at.tzinfo is None:
        raise Unprocessable("client_at needs a time zone.")
    return now if client_at is None or client_at > now else client_at


def accept_event(db: Session, user_id: uuid.UUID, item_id: uuid.UUID, client_at: datetime | None) -> bool:
    """True when this event is the newest for the lesson (and records it); False for a stale event (ignore it)."""
    at = _when(db, client_at)
    row = db.execute(
        insert(LessonEventClock)
        .values(user_id=user_id, item_id=item_id, client_at=at)
        .on_conflict_do_update(
            index_elements=["user_id", "item_id"],
            set_={"client_at": at},
            where=LessonEventClock.client_at < at,
        )
        .returning(LessonEventClock.client_at)
    ).first()
    return row is not None


def record_position(
    db: Session, user_id: uuid.UUID, lesson_id: uuid.UUID, block_index: int, client_at: datetime | None
) -> dict[str, Any]:
    """Save where the learner is (a readable live lesson); an older event leaves the newer position in place."""
    from portal_api.modules.content.completion import _readable_lesson

    item = _readable_lesson(db, user_id, lesson_id)
    if item.chapter_id is None:
        raise NotFound("Lesson not found.")
    at = _when(db, client_at)
    db.execute(
        insert(ReadingPosition)
        .values(user_id=user_id, chapter_id=item.chapter_id, lesson_id=item.id, block_index=block_index, client_at=at)
        .on_conflict_do_update(
            index_elements=["user_id", "chapter_id"],
            set_={"lesson_id": item.id, "block_index": block_index, "client_at": at, "updated_at": func.now()},
            where=ReadingPosition.client_at < at,
        )
    )
    db.commit()
    current = position(db, user_id, item.chapter_id)
    assert current is not None
    return current


def position(db: Session, user_id: uuid.UUID, chapter_id: uuid.UUID) -> dict[str, Any] | None:
    """The saved place in this chapter, if its lesson is still live (a withdrawn lesson is never offered)."""
    from portal_api.modules.content.models import Availability, ContentItem

    row = db.get(ReadingPosition, (user_id, chapter_id))
    if row is None:
        return None
    item = db.get(ContentItem, row.lesson_id)
    if item is None or item.availability != Availability.live.value:
        return None
    return {
        "chapter_id": row.chapter_id,
        "lesson_id": row.lesson_id,
        "lesson_title": item.title,
        "block_index": row.block_index,
        "client_at": row.client_at,
    }
