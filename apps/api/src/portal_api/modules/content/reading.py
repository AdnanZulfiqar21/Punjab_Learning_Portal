"""One topic, one lesson (TOPIC-READER-01).

Published lessons follow the same entitlement rules as the chapter list. A draft is returned only to staff who can
draft, review or publish that class and subject, or to an owner_admin whose grant covers it. Learners receive no
draft text, asset ids or page numbers. Several lesson concepts for one topic are a conflict, never a silent pick.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from portal_api.config import get_settings
from portal_api.errors import Conflict, NotFound
from portal_api.modules.access import service as access
from portal_api.modules.content import assets, kinds
from portal_api.modules.content.models import Availability as ItemAvailability
from portal_api.modules.content.models import ContentItem, ContentVersion
from portal_api.modules.content.schemas import (
    BookExerciseOut,
    BookExercisesOut,
    BookPaperOut,
    TopicLessonOut,
    TopicReadingOut,
)
from portal_api.modules.content.workflow import roles_in_scope
from portal_api.modules.curriculum import service as curriculum
from portal_api.modules.curriculum.models import (
    EXERCISE_KEY_SUFFIX,
    MCQ_KEY_SUFFIX,
    PAPER_KEY_SUFFIXES,
    SHORT_KEY_SUFFIX,
    BookEdition,
    Chapter,
    Topic,
    TopicKind,
)
from portal_api.modules.curriculum.regions import book_is_released
from portal_api.modules.identity.deps import Principal
from portal_api.modules.identity.permissions import Permission, Role, permissions_for

Language = Literal["en", "ur", "roman_ur"]
Availability = Literal["published", "private_preview", "unavailable"]
_PREVIEW_ROLES = {Role.content_author, Role.subject_reviewer, Role.publisher, Role.owner_admin}
_PREVIEW_PERMS = {Permission.draft_content, Permission.review_content, Permission.publish_content}


def reading(
    db: Session,
    who: Principal | None,
    topic_id: uuid.UUID,
    language: Language | None,
) -> TopicReadingOut:
    place = _located(db, topic_id)

    def out(availability: Availability, lesson: TopicLessonOut | None) -> TopicReadingOut:
        return TopicReadingOut(
            topic_id=place.topic_id,
            number=place.number,
            title=place.title,
            chapter_id=place.chapter_id,
            chapter_number=place.chapter_number,
            chapter_title=place.chapter_title,
            grade_number=place.grade,
            subject_name=place.subject_name,
            previous_topic_id=place.previous_id,
            next_topic_id=place.next_id,
            chapter_start=place.parent_id is None and place.previous_id is None and not place.practice_only,
            kind=place.kind,
            availability=availability,
            lesson=lesson,
        )

    published = _concepts(db, place.topic_id, published_only=True)
    if len(published) > 1:
        raise Conflict("This topic has more than one published lesson. None is chosen automatically.")
    if published:
        return out("published", _published_lesson(db, who, place.grade, place.subject_code, published[0], language))
    if _can_preview(db, who, place.grade, place.subject_code):
        drafts = _concepts(db, place.topic_id, published_only=False)
        if len(drafts) > 1:
            raise Conflict("This topic has more than one draft lesson. None is chosen automatically.")
        if drafts:
            draft = _draft_lesson(drafts[0], language)
            if draft is not None:
                return out("private_preview", draft)
    return out("unavailable", None)


def book_exercises(db: Session, who: Principal | None, grade: int, subject: str) -> BookExercisesOut:
    """BOOK-EXERCISES-01: each chapter's end-of-chapter exercise in this class's book, in chapter order, with whether
    its lesson can be read by this caller (the same rule as `reading`, without sending any lesson text).

    BOOK-PAPERS-01: the Board papers printed at the end of the same book come with them, in book order."""
    book = curriculum.book_for(db, grade, subject)
    preview = _can_preview(db, who, book.grade.number, book.subject.code)

    def rows(*suffixes: str) -> Sequence[tuple[Topic, Chapter]]:
        return db.execute(
            select(Topic, Chapter)
            .join(Chapter, Topic.chapter_id == Chapter.id)
            .where(
                Chapter.book_id == book.id,
                Chapter.retired_at.is_(None),
                Topic.retired_at.is_(None),
                or_(*(Topic.natural_key.endswith(suffix, autoescape=True) for suffix in suffixes)),
            )
            .order_by(Chapter.display_order, Topic.display_order)
        ).all()

    exercises: list[BookExerciseOut] = []
    for topic, chapter in rows(EXERCISE_KEY_SUFFIX):
        availability, languages = _listed_availability(db, topic, preview)
        exercises.append(
            BookExerciseOut(
                topic_id=topic.id,
                chapter_id=chapter.id,
                chapter_number=chapter.number,
                chapter_title=chapter.title,
                availability=availability,
                available_languages=languages,  # type: ignore[arg-type]
            )
        )
    # PRACTICE-MCQ-01 / PRACTICE-SHORT-01: the chapters' own practice sets, each kind in chapter order.
    sets: dict[str, list[BookExerciseOut]] = {MCQ_KEY_SUFFIX: [], SHORT_KEY_SUFFIX: []}
    for suffix, found in sets.items():
        for topic, chapter in rows(suffix):
            availability, languages = _listed_availability(db, topic, preview)
            found.append(
                BookExerciseOut(
                    topic_id=topic.id,
                    chapter_id=chapter.id,
                    chapter_number=chapter.number,
                    chapter_title=chapter.title,
                    availability=availability,
                    available_languages=languages,  # type: ignore[arg-type]
                )
            )
    papers: list[BookPaperOut] = []
    for topic, _chapter in rows(*PAPER_KEY_SUFFIXES):
        availability, languages = _listed_availability(db, topic, preview)
        papers.append(
            BookPaperOut(
                topic_id=topic.id,
                title=topic.title,
                availability=availability,
                available_languages=languages,  # type: ignore[arg-type]
            )
        )
    return BookExercisesOut(
        grade_number=book.grade.number,
        subject_code=book.subject.code,
        subject_name=book.subject.name,
        chapter_label=book.chapter_label,
        exercises=exercises,
        papers=papers,
        mcq_sets=sets[MCQ_KEY_SUFFIX],
        short_sets=sets[SHORT_KEY_SUFFIX],
    )


def _listed_availability(db: Session, topic: Topic, preview: bool) -> tuple[Availability, list[str]]:
    """Whether a listed Practice topic's lesson can be read, and in which languages, without loading any text."""
    published = _concepts(db, topic.id, published_only=True)
    if len(published) == 1:
        return "published", sorted({item.language for item in published[0]})
    if not published and preview:
        drafts = _concepts(db, topic.id, published_only=False)
        variants = drafts[0] if len(drafts) == 1 else []
        usable = [item for item in variants if item.working is not None and _has_body(item.working)]
        if usable:
            return "private_preview", sorted({item.language for item in usable})
    return "unavailable", []


def preview_asset(db: Session, who: Principal, topic_id: uuid.UUID, version_id: uuid.UUID) -> tuple[bytes, str]:
    """A delivery copy named by this topic's private-preview lesson. Not a public file route."""
    topic, _chapter, book = _place(db, topic_id)
    if not _can_preview(db, who, book.grade.number, book.subject.code):
        raise NotFound("File not found.")
    drafts = _concepts(db, topic.id, published_only=False)
    if len(drafts) != 1:
        raise NotFound("File not found.")
    named = {vid for item in drafts[0] for _where, vid, _kind in assets.block_refs(_working(item).body)}
    if str(version_id) not in named:
        raise NotFound("File not found.")
    version = db.get(assets.AssetVersion, version_id)
    asset = db.get(assets.Asset, version.asset_id) if version is not None else None
    if (
        version is None
        or asset is None
        or asset.kind not in assets.SERVED
        or version.delivery_state != "ready"
        or not version.delivery_key
        or (asset.grade_number, asset.subject_code) != (book.grade.number, book.subject.code)
    ):
        raise NotFound("File not found.")
    media = version.delivery_media_type or "application/octet-stream"
    return assets.read(version.delivery_key), media


def _place(db: Session, topic_id: uuid.UUID) -> tuple[Topic, Chapter, BookEdition]:
    topic = db.get(Topic, topic_id)
    if topic is None or topic.retired_at is not None:
        raise NotFound("Topic not found.")
    chapter = db.get(Chapter, topic.chapter_id)
    book = db.get(BookEdition, chapter.book_id) if chapter is not None else None
    if chapter is None or chapter.retired_at is not None or book is None or not book_is_released(db, book):
        raise NotFound("Topic not found.")
    return topic, chapter, book


@dataclass(frozen=True)
class _Place:
    """Where a topic sits: everything `reading` needs from the catalogue, as plain values (no ORM rows)."""

    topic_id: uuid.UUID
    number: str | None
    title: str
    kind: TopicKind
    parent_id: uuid.UUID | None
    practice_only: bool
    chapter_id: uuid.UUID
    chapter_number: int
    chapter_title: str
    grade: int
    subject_name: str
    subject_code: str
    previous_id: uuid.UUID | None
    next_id: uuid.UUID | None


_places: dict[uuid.UUID, tuple[float, _Place]] = {}
_places_lock = threading.Lock()
_PLACES_MAX = 20_000


def _located(db: Session, topic_id: uuid.UUID) -> _Place:
    """READING-PLACE-CACHE-01: a topic's place in the catalogue and its reading-order neighbours, kept per process for
    `reading_place_cache_s` (60 s; 0 = off). Every lesson read needed four catalogue lookups and the whole chapter's
    topic list for this, about half the request's work, for data that changes only with a catalogue import; the public
    chapter route already lets it be cached for the same minute. A retired topic or chapter, or a region withdrawn,
    is therefore noticed within that minute. Lessons, their availability and the caller's access are never cached
    here: they are read on every request. A topic that is not found is not cached."""
    ttl = get_settings().reading_place_cache_s
    now = time.monotonic()
    if ttl > 0:
        with _places_lock:
            hit = _places.get(topic_id)
        if hit is not None and now - hit[0] < ttl:
            return hit[1]
    topic, chapter, book = _place(db, topic_id)
    previous_id, next_id = _neighbours(db, topic)
    place = _Place(
        topic_id=topic.id,
        number=topic.number,
        title=topic.title,
        kind=topic.kind,
        parent_id=topic.parent_id,
        practice_only=topic.practice_only,
        chapter_id=chapter.id,
        chapter_number=chapter.number,
        chapter_title=chapter.title,
        grade=book.grade.number,
        subject_name=book.subject.name,
        subject_code=book.subject.code,
        previous_id=previous_id,
        next_id=next_id,
    )
    if ttl > 0:
        with _places_lock:
            if len(_places) >= _PLACES_MAX:
                _places.clear()
            _places[topic_id] = (now, place)
    return place


def forget_places() -> None:
    """Tests and tools: drop every cached place."""
    with _places_lock:
        _places.clear()


def _neighbours(db: Session, topic: Topic) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """The topics before and after this one in the book's reading order: each topic, then its subtopics, then the next
    topic (1.2, 1.2.1, 1.2.2, 1.2.2.1, …, 1.3). Siblings alone skipped every subtopic (owner, 2026-10-28).

    BOOK-EXERCISES-01: the end-of-chapter exercise (and anything under it) is not in that order, so Learn never leads
    into it, and the exercise itself has no neighbours: it is opened from Practice. BOOK-PAPERS-01: the same for the
    Board papers at the end of the book (every Practice-only kind)."""
    if topic.practice_only:
        return None, None
    rows = list(
        db.scalars(
            select(Topic)
            .where(Topic.chapter_id == topic.chapter_id, Topic.retired_at.is_(None))
            .order_by(Topic.display_order, Topic.id)
        )
    )
    children: dict[uuid.UUID | None, list[Topic]] = {}
    for row in rows:
        children.setdefault(row.parent_id, []).append(row)
    ids: list[uuid.UUID] = []

    def walk(parent: uuid.UUID | None) -> None:
        for row in children.get(parent, []):
            if row.practice_only:
                continue
            ids.append(row.id)
            walk(row.id)

    walk(None)
    if topic.id not in ids:
        return None, None
    index = ids.index(topic.id)
    previous_id = ids[index - 1] if index > 0 else None
    next_id = ids[index + 1] if index + 1 < len(ids) else None
    return previous_id, next_id


def _can_preview(db: Session, who: Principal | None, grade: int, subject: str) -> bool:
    if who is None:
        return False
    roles = roles_in_scope(db, who.user.id, grade, subject)
    if Role.owner_admin in roles:
        return True
    return bool(permissions_for(roles) & _PREVIEW_PERMS) and bool(roles & _PREVIEW_ROLES)


def _concepts(db: Session, topic_id: uuid.UUID, *, published_only: bool) -> list[list[ContentItem]]:
    statement = select(ContentItem).where(
        ContentItem.topic_id == topic_id,
        ContentItem.kind.in_([k.name for k in kinds.KINDS.values() if k.learner_readable]),
    )
    if published_only:
        statement = statement.where(ContentItem.availability == ItemAvailability.live.value)
    else:
        statement = statement.where(ContentItem.availability != ItemAvailability.live.value)
    grouped: dict[uuid.UUID, list[ContentItem]] = {}
    for item in db.scalars(statement.order_by(ContentItem.created_at, ContentItem.id)):
        grouped.setdefault(item.concept_id or item.id, []).append(item)
    return list(grouped.values())


def _published_lesson(
    db: Session,
    who: Principal | None,
    grade: int,
    subject_code: str,
    variants: list[ContentItem],
    language: Language | None,
) -> TopicLessonOut:
    item = _pick(variants, language)
    version = item.published
    assert version is not None
    entitled = who is not None and access.entitled_for(db, who.user.id, access.Need.subjects(grade, subject_code))
    locked = item.access_tier != "preview" and not entitled
    return TopicLessonOut(
        id=item.id,
        title=item.title,
        language=item.language,  # type: ignore[arg-type]
        available_languages=sorted({row.language for row in variants}),
        requested_language_missing=bool(language) and item.language != language,
        topic_id=item.topic_id or item.id,
        version=version.number,
        status="published",
        private_preview=False,
        access_tier=item.access_tier,  # type: ignore[arg-type]
        locked=locked,
        content_schema_version=version.content_schema_version,
        block_types=[] if locked else version.block_types,
        body=None if locked else version.body,
        source_refs=[],
    )


def _draft_lesson(variants: list[ContentItem], language: Language | None) -> TopicLessonOut | None:
    # A draft may be the book's heading alone (Chemistry 11 14.4 runs straight into 14.4.1); it is still that topic's
    # lesson, and the reader goes on with the first subtopic under it (BOOK-HEADING-01). An empty draft is not.
    usable = [item for item in variants if _has_body(_working(item))]
    if not usable:
        return None
    item = _pick(usable, language)
    version = _working(item)
    return TopicLessonOut(
        id=item.id,
        title=item.title,
        language=item.language,  # type: ignore[arg-type]
        available_languages=sorted({row.language for row in usable}),
        requested_language_missing=bool(language) and item.language != language,
        topic_id=item.topic_id or item.id,
        version=version.number,
        status=item.state,  # type: ignore[arg-type]
        private_preview=True,
        access_tier=item.access_tier,  # type: ignore[arg-type]
        locked=False,
        content_schema_version=version.content_schema_version,
        block_types=version.block_types,
        body=version.body,
        source_refs=version.source_refs,
    )


def _pick(variants: list[ContentItem], language: Language | None) -> ContentItem:
    if language:
        wanted = [item for item in variants if item.language == language]
        if wanted:
            return wanted[0]
    english = [item for item in variants if item.language == "en"]
    return english[0] if english else variants[0]


def _working(item: ContentItem) -> ContentVersion:
    version = item.working
    if version is None:
        raise Conflict("This lesson has no working version.")
    return version


def _has_body(version: ContentVersion) -> bool:
    blocks = version.body.get("blocks") if isinstance(version.body, dict) else None
    return isinstance(blocks, list) and any(isinstance(block, dict) for block in blocks)
