"""Practice form generation (P09.S1.T1, P09.S3) and keyless learner snapshots (P08.S2.T3).

The pool is every *published, live* question in the requested chapters/topics, grouped by canonical family so a form
never contains two variants of one question. Selection uses a stored random seed (auditable, reproducible). If the
approved pool can't satisfy the request, generation fails honestly with the available count; it never silently
changes the test. The frozen form records versions, option permutations, marks, timing and the scoring policy.
"""

from __future__ import annotations

import hashlib
import json
import random
import secrets
import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from portal_api.errors import Conflict, NotFound, Unprocessable
from portal_api.modules.assessment.models import FormItem, PracticeForm
from portal_api.modules.content.models import Availability, ContentItem, ContentVersion
from portal_api.modules.curriculum.models import BookEdition, Chapter, Grade, Subject, Topic
from portal_api.modules.identity.deps import Principal

SELF_PACED_TOLERANCE_MS = 3000  # §10.5 default for self-paced timed practice; ranked mocks pin 0


def _pool(
    db: Session,
    grade: int,
    subject: str,
    chapter_ids: list[uuid.UUID],
    topic_ids: list[uuid.UUID],
    question_pool: str = "practice",
) -> dict[uuid.UUID, list[tuple[ContentItem, ContentVersion]]]:
    stmt = (
        select(ContentItem, ContentVersion)
        .join(ContentVersion, ContentVersion.id == ContentItem.published_version_id)
        .where(
            ContentItem.kind == "mcq",
            ContentItem.availability == Availability.live.value,  # quarantined/retired never count
            ContentItem.grade_number == grade,
            ContentItem.subject_code == subject,
            ContentItem.chapter_id.in_(chapter_ids),
        )
    )
    if question_pool != "any":  # P08.S3.T3: mock-reserved questions never reach practice tests
        stmt = stmt.where(ContentItem.question_pool == question_pool)
    if topic_ids:
        stmt = stmt.where(ContentItem.topic_id.in_(topic_ids))
    families: dict[uuid.UUID, list[tuple[ContentItem, ContentVersion]]] = defaultdict(list)
    for item, version in db.execute(stmt).all():
        families[item.family_id or item.id].append((item, version))
    return families


def _book_chapters(db: Session, grade: int, subject: str) -> list[Chapter]:
    return list(
        db.scalars(
            select(Chapter)
            .join(BookEdition, BookEdition.id == Chapter.book_id)
            .join(Grade, Grade.id == BookEdition.grade_id)
            .join(Subject, Subject.id == BookEdition.subject_id)
            .where(Grade.number == grade, Subject.code == subject, Subject.active, Chapter.retired_at.is_(None))
            .order_by(Chapter.display_order)
        )
    )


def availability(db: Session, grade: int, subject: str) -> list[dict[str, Any]]:
    """Approved, published question families per chapter (counts only; nothing about the questions themselves)."""
    chapters = _book_chapters(db, grade, subject)
    if not chapters:
        raise NotFound("No book is available for this class and subject.")
    counts = dict(
        db.execute(
            select(
                ContentItem.chapter_id, func.count(func.distinct(func.coalesce(ContentItem.family_id, ContentItem.id)))
            )
            .where(
                ContentItem.kind == "mcq",
                ContentItem.availability == Availability.live.value,
                ContentItem.question_pool == "practice",
                ContentItem.grade_number == grade,
                ContentItem.subject_code == subject,
            )
            .group_by(ContentItem.chapter_id)
        ).all()
    )
    return [
        {"chapter_id": c.id, "number": c.number, "title": c.title, "questions": int(counts.get(c.id, 0))}
        for c in chapters
    ]


def _request_hash(req: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(req, sort_keys=True, default=str).encode()).hexdigest()


def create_form(
    db: Session,
    who: Principal,
    *,
    idempotency_key: str,
    grade: int,
    subject: str,
    chapter_ids: list[uuid.UUID],
    topic_ids: list[uuid.UUID],
    question_count: int,
    timed_minutes: int | None,
    feedback_mode: str,
    scope_mode: str = "chapters",
    half: int | None = None,
) -> PracticeForm:
    req = {
        "grade": grade,
        "subject": subject,
        "scope": scope_mode,
        "half": half,
        "chapter_ids": sorted(map(str, chapter_ids)),
        "topic_ids": sorted(map(str, topic_ids)),
        "question_count": question_count,
        "timed_minutes": timed_minutes,
        "feedback_mode": feedback_mode,
    }
    rhash = _request_hash(req)
    existing = db.scalar(
        select(PracticeForm).where(
            PracticeForm.owner_id == who.user.id, PracticeForm.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        if existing.request_hash != rhash:
            raise Conflict("This request key was already used for a different test.")
        return existing

    from portal_api.modules.access import service as access

    access.require_access(db, who.user.id, purpose="Practice tests")
    grades = [11, 12] if scope_mode == "combined" else [grade]
    book = _book_chapters(db, grade, subject)
    if scope_mode != "chapters" and topic_ids:
        raise Unprocessable("Topics can only be chosen for a chapter test.")
    if scope_mode == "full_book":
        chapter_ids = [c.id for c in book]
    elif scope_mode == "half_book":
        if half not in (1, 2):
            raise Unprocessable("Choose the first or second half of the book.")
        split = (len(book) + 1) // 2  # by the book's own chapter order, never by page numbers
        chapter_ids = [c.id for c in (book[:split] if half == 1 else book[split:])]
    elif scope_mode == "combined":
        chapter_ids = [c.id for g in grades for c in _book_chapters(db, g, subject)]
    valid = {c.id for g in grades for c in _book_chapters(db, g, subject)}
    if not chapter_ids or not set(chapter_ids) <= valid:
        raise Unprocessable("Choose chapters from this class and subject's book.")
    if topic_ids:
        topics = db.scalars(select(Topic).where(Topic.id.in_(topic_ids), Topic.retired_at.is_(None))).all()
        if len(topics) != len(set(topic_ids)) or any(t.chapter_id not in set(chapter_ids) for t in topics):
            raise Unprocessable("Topics must belong to the chosen chapters.")
    pool: dict[uuid.UUID, list[tuple[ContentItem, ContentVersion]]] = {}
    for g in grades:
        pool.update(_pool(db, g, subject, chapter_ids, topic_ids))
    if len(pool) < question_count:
        raise Unprocessable(
            f"Only {len(pool)} approved question(s) are available for this selection; {question_count} were requested.",
            available=len(pool),
            requested=question_count,
        )

    seed = secrets.randbits(62)
    rng = random.Random(seed)  # noqa: S311 - reproducible sampling from a stored seed, not a secret
    chosen = rng.sample(sorted(pool, key=str), question_count)
    form = PracticeForm(
        id=uuid.uuid4(),
        owner_id=who.user.id,
        idempotency_key=idempotency_key,
        request_hash=rhash,
        kind="practice",
        grade_number=grade,
        subject_code=subject,
        scope={
            "mode": scope_mode,
            "grades": grades,
            "half": half,
            "chapter_ids": sorted(map(str, chapter_ids)),
            "topic_ids": req["topic_ids"],
        },
        seed=seed,
        question_count=question_count,
        duration_s=timed_minutes * 60 if timed_minutes else None,
        late_write_tolerance_ms=SELF_PACED_TOLERANCE_MS if timed_minutes else 0,
        feedback_mode=feedback_mode,
        negative_marks=0,
        invalid_item_treatment="EXCLUDE",
    )
    db.add(form)
    for position, family in enumerate(chosen, start=1):
        item, version = rng.choice(sorted(pool[family], key=lambda iv: str(iv[0].id)))
        option_ids = [o["id"] for o in version.body["options"]]
        if version.body.get("shuffle_options", True):
            rng.shuffle(option_ids)  # option IDs never change; only their display order does
        db.add(
            FormItem(
                form_id=form.id,
                position=position,
                item_id=item.id,
                family_id=family,
                version_id=version.id,
                marks=int(version.body.get("marks", 1)),
                option_order=option_ids,
            )
        )
    try:
        db.commit()
    except IntegrityError:  # a concurrent request with the same key won; return its form
        db.rollback()
        winner = db.scalar(
            select(PracticeForm).where(
                PracticeForm.owner_id == who.user.id, PracticeForm.idempotency_key == idempotency_key
            )
        )
        if winner is None or winner.request_hash != rhash:
            raise Conflict("This request key was already used for a different test.") from None
        return winner
    db.refresh(form)
    return form


def learner_items(db: Session, form: PracticeForm) -> list[dict[str, Any]]:
    """Keyless snapshot: stems and options in the frozen order. Never includes keys or explanations."""
    out: list[dict[str, Any]] = []
    for fi in form.items:
        version = db.get(ContentVersion, fi.version_id)
        assert version is not None
        options = {o["id"]: o for o in version.body["options"]}
        out.append(
            {
                "position": fi.position,
                "marks": fi.marks,
                "stem": version.body["stem"],
                "options": [{"id": oid, "blocks": options[oid]["blocks"]} for oid in fi.option_order],
            }
        )
    return out


def superseded_positions(db: Session, form: PracticeForm) -> list[int]:
    """Positions whose frozen question version is no longer the live published version (quarantined, retired,
    corrected or replaced since the form was built)."""
    out = []
    for fi in form.items:
        item = db.get(ContentItem, fi.item_id)
        if item is None or item.availability != Availability.live.value or item.published_version_id != fi.version_id:
            out.append(fi.position)
    return out


def item_keys(db: Session, form: PracticeForm) -> dict[int, dict[str, Any]]:
    """Frozen keys and explanations per position. Server-side only: scoring and post-release review."""
    out: dict[int, dict[str, Any]] = {}
    for fi in form.items:
        version = db.get(ContentVersion, fi.version_id)
        assert version is not None
        out[fi.position] = {
            "correct_option_id": version.body["correct_option_id"],
            "option_ids": tuple(fi.option_order),
            "marks": fi.marks,
            "explanation": version.body.get("explanation", {}),
            "stem": version.body["stem"],
            "options": {o["id"]: o for o in version.body["options"]},
        }
    return out
