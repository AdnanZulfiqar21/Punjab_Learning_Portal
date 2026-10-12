"""Live lessons related to a question (P12.S1.T2 REVIEW-LINKS-01; W07.S2.T1 NEXT-STEPS-01).

One rule for every result screen: the published, live lessons for the question's topic, or for its chapter when the
topic has none (or the question has no topic). One link per lesson concept (the original, whatever its language).
Drafts, quarantined and retired lessons are never linked.
"""

from __future__ import annotations

import uuid
from collections.abc import Hashable, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.modules.content.models import Availability, ContentItem, ContentVersion


def live_lessons_for[K: Hashable](
    db: Session, questions: Mapping[K, ContentItem], limit: int = 3
) -> dict[K, list[ContentItem]]:
    """For each question, up to `limit` live lessons (topic first, else chapter), in publication order."""
    chapters = {q.chapter_id for q in questions.values()}
    if not chapters:
        return {}
    lessons = (
        db.execute(
            select(ContentItem)
            .join(ContentVersion, ContentVersion.id == ContentItem.published_version_id)
            .where(
                ContentItem.kind == "lesson",
                ContentItem.availability == Availability.live.value,
                ContentItem.chapter_id.in_(chapters),
                ContentItem.concept_id.is_(None),
            )
            .order_by(ContentVersion.published_at, ContentItem.id)
        )
        .scalars()
        .all()
    )
    by_topic: dict[uuid.UUID, list[ContentItem]] = {}
    by_chapter: dict[uuid.UUID, list[ContentItem]] = {}
    for lesson in lessons:
        by_chapter.setdefault(lesson.chapter_id, []).append(lesson)
        if lesson.topic_id:
            by_topic.setdefault(lesson.topic_id, []).append(lesson)
    out: dict[K, list[ContentItem]] = {}
    for key, q in questions.items():
        picks = (by_topic.get(q.topic_id) if q.topic_id else None) or by_chapter.get(q.chapter_id, [])
        out[key] = picks[:limit]
    return out
