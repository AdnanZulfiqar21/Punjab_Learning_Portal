"""Book mistakes: every printed error of one textbook, by chapter and topic (BOOK-MISTAKES-01, owner 2026-11-12).

The English lessons keep the book's printed wording, errors included (BOOK-CORRECTION-01): the wrong passages are marked
in red (`book_errors`) and a green `correction` box after them gives the right version. This module gathers those boxes
from the book's English lessons so a learner can see all of a book's mistakes in one place. It adds no text of its own:
each mistake is the lesson's own blocks, the marked printed passage and its correction box.

Lessons follow the same rules as reading a topic (`reading.py`): learners see published lessons only, staff who can
draft, review or publish the class and subject also see drafts, and a premium lesson's text goes only to an entitled
caller. A locked or unreadable topic is still counted (a count is not lesson text) but its mistakes are not sent.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.errors import NotFound
from portal_api.modules.access import service as access
from portal_api.modules.content import kinds
from portal_api.modules.content.models import Availability as ItemAvailability
from portal_api.modules.content.models import ContentItem, ContentVersion
from portal_api.modules.content.reading import _can_preview
from portal_api.modules.content.schemas import (
    BookMistakeChapterOut,
    BookMistakeOut,
    BookMistakesOut,
    BookMistakeTopicOut,
)
from portal_api.modules.curriculum import service as curriculum
from portal_api.modules.curriculum.models import BookEdition, Chapter, Topic
from portal_api.modules.curriculum.regions import book_is_released
from portal_api.modules.identity.deps import Principal

Block = dict[str, Any]


def _is_correction(block: object) -> bool:
    return isinstance(block, dict) and block.get("type") == "callout" and block.get("tone") == "correction"


def mistakes_in(blocks: Iterable[object]) -> list[BookMistakeOut]:
    """Each correction box with the printed passage it corrects.

    The passage is every block carrying red book-error marks since the previous correction. A correction that follows
    a block without marks (a printed figure or question that is wrong as a whole) takes that block. Boxes that follow
    one another directly correct the same passage, so they stay together."""
    found: list[BookMistakeOut] = []
    since: list[Block] = []  # blocks after the previous correction
    last: Block | None = None  # the latest block that is not a correction
    previous_was_correction = False
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if _is_correction(block):
            if previous_was_correction and found:
                found[-1].corrections.append(block)
            else:
                marked = [b for b in since if b.get("book_errors")]
                context = marked or ([last] if last is not None else [])
                found.append(BookMistakeOut(context=context, corrections=[block]))
            since = []
            previous_was_correction = True
            continue
        since.append(block)
        last = block
        previous_was_correction = False
    return found


@dataclass
class _Lesson:
    availability: Literal["published", "private_preview"]
    item: ContentItem | None = None
    version_id: uuid.UUID | None = None
    blocks: list[object] = field(default_factory=list)


def _reading_order(topics: Sequence[Topic]) -> list[Topic]:
    """The book's reading order (each topic, then its subtopics), then the Practice-only topics (the exercise)."""
    children: dict[uuid.UUID | None, list[Topic]] = {}
    for topic in sorted(topics, key=lambda t: (t.display_order, str(t.id))):
        children.setdefault(topic.parent_id, []).append(topic)
    ordered: list[Topic] = []

    def walk(parent: uuid.UUID | None) -> None:
        for topic in children.get(parent, []):
            ordered.append(topic)
            walk(topic.id)

    walk(None)
    seen = {t.id for t in ordered}
    ordered += [t for t in topics if t.id not in seen]  # an orphaned subtopic is still listed, never dropped
    reading = [t for t in ordered if not t.practice_only]
    return reading + [t for t in ordered if t.practice_only]


def _lessons(db: Session, topic_ids: list[uuid.UUID], preview: bool) -> dict[uuid.UUID, _Lesson]:
    """Each topic's English lesson, chosen as `reading.reading` chooses it (one published concept; otherwise one draft
    concept for staff). Several concepts for one topic are a conflict there, so here the topic is left out."""
    if not topic_ids:
        return {}
    items = db.scalars(
        select(ContentItem)
        .where(
            ContentItem.topic_id.in_(topic_ids),
            ContentItem.kind.in_([k.name for k in kinds.KINDS.values() if k.learner_readable]),
        )
        .order_by(ContentItem.created_at, ContentItem.id)
    ).all()
    by_topic: dict[uuid.UUID, dict[bool, dict[uuid.UUID, list[ContentItem]]]] = {}
    for item in items:
        assert item.topic_id is not None
        live = item.availability == ItemAvailability.live.value
        concepts = by_topic.setdefault(item.topic_id, {True: {}, False: {}})[live]
        concepts.setdefault(item.concept_id or item.id, []).append(item)
    chosen: dict[uuid.UUID, _Lesson] = {}
    for topic_id, groups in by_topic.items():
        published, drafts = list(groups[True].values()), list(groups[False].values())
        if len(published) == 1:
            english = [i for i in published[0] if i.language == "en"]
            if english and english[0].published_version_id:
                chosen[topic_id] = _Lesson("published", english[0], english[0].published_version_id)
        elif not published and preview and len(drafts) == 1:
            english = [i for i in drafts[0] if i.language == "en"]
            if english and english[0].working_version_id:
                chosen[topic_id] = _Lesson("private_preview", english[0], english[0].working_version_id)
    ids = [lesson.version_id for lesson in chosen.values() if lesson.version_id]
    bodies = {
        version_id: body
        for version_id, body in db.execute(
            select(ContentVersion.id, ContentVersion.body).where(ContentVersion.id.in_(ids))
        ).all()
    }
    for lesson in chosen.values():
        body = bodies.get(lesson.version_id) if lesson.version_id else None
        found = body.get("blocks") if isinstance(body, dict) else None
        lesson.blocks = found if isinstance(found, list) else []
    return chosen


def _gather(
    db: Session, who: Principal | None, book: BookEdition, chapters: Sequence[Chapter], *, with_text: bool
) -> BookMistakesOut:
    grade, subject = book.grade.number, book.subject.code
    preview = _can_preview(db, who, grade, subject)
    entitled = who is not None and access.entitled_for(db, who.user.id, access.Need.subjects(grade, subject))
    topics = db.scalars(
        select(Topic).where(Topic.chapter_id.in_([c.id for c in chapters]), Topic.retired_at.is_(None))
    ).all()
    lessons = _lessons(db, [t.id for t in topics], preview)
    per_chapter: dict[uuid.UUID, list[Topic]] = {}
    for topic in topics:
        per_chapter.setdefault(topic.chapter_id, []).append(topic)

    out: list[BookMistakeChapterOut] = []
    for chapter in chapters:
        listed: list[BookMistakeTopicOut] = []
        for topic in _reading_order(per_chapter.get(chapter.id, [])):
            lesson = lessons.get(topic.id)
            if lesson is None or lesson.item is None:
                continue
            found = mistakes_in(lesson.blocks)
            if not found:
                continue
            # As in `reading`: a staff preview of a draft is never locked; a published premium lesson needs a plan.
            locked = lesson.availability == "published" and lesson.item.access_tier != "preview" and not entitled
            listed.append(
                BookMistakeTopicOut(
                    topic_id=topic.id,
                    number=topic.number,
                    title=topic.title,
                    practice_only=topic.practice_only,
                    availability=lesson.availability,
                    lesson_id=lesson.item.id,
                    locked=locked,
                    count=len(found),
                    mistakes=found if with_text and not locked else [],
                )
            )
        out.append(
            BookMistakeChapterOut(
                chapter_id=chapter.id,
                number=chapter.number,
                title=chapter.title,
                count=sum(t.count for t in listed),
                topics=listed,
            )
        )
    return BookMistakesOut(
        grade_number=grade,
        subject_code=subject,
        subject_name=book.subject.name,
        chapter_label=book.chapter_label,
        total=sum(c.count for c in out),
        chapters=out,
    )


def _chapters(db: Session, book: BookEdition) -> list[Chapter]:
    return list(
        db.scalars(
            select(Chapter)
            .where(Chapter.book_id == book.id, Chapter.retired_at.is_(None))
            .order_by(Chapter.display_order, Chapter.id)
        )
    )


def book_mistakes(db: Session, who: Principal | None, grade: int, subject: str) -> BookMistakesOut:
    """The whole book: how many printed mistakes each chapter and topic has (counts only, no lesson text)."""
    book = curriculum.book_for(db, grade, subject)
    return _gather(db, who, book, _chapters(db, book), with_text=False)


def chapter_mistakes(db: Session, who: Principal | None, chapter_id: uuid.UUID) -> BookMistakesOut:
    """One chapter: each topic's printed mistakes with their corrections, as the lesson shows them."""
    chapter = db.get(Chapter, chapter_id)
    book = db.get(BookEdition, chapter.book_id) if chapter is not None else None
    if chapter is None or chapter.retired_at is not None or book is None or not book_is_released(db, book):
        raise NotFound("Chapter not found.")
    return _gather(db, who, book, [chapter], with_text=True)
