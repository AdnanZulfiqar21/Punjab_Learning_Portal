"""Learner dashboard (roadmap P11.S1.T2, §6.6; DASHBOARD-01).

One request for the signed-in home page: what to continue, today's revision, the next scheduled mock, recent results
and the three progress meters, each with its definition. The meters stay separate and are never blended:

* **Syllabus coverage** needs verified inclusion records (P05.S2) for the learner's exam outcomes (B02). Book topics
  are not syllabus outcomes, so until those records exist the meter is unavailable, as in EVIDENCE-RULES-01.
* **Content completed** = completed live lessons ÷ live lessons in the profile's books (`completion`).
* **Demonstrated knowledge** = topics classified `demonstrated` under `evidence_rules_v2` ÷ topics in those books;
  "not enough evidence yet" until at least one of those topics has enough evidence to be classified.

A missing profile or a zero denominator gives an explanation instead of a percentage. Class XI and XII are never
mixed: the scope is the profile's one class.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from portal_api.modules.assessment import forms

DEFINITIONS = {
    "syllabus_coverage": "Outcomes in your class and subjects that have published content ÷ outcomes in your "
    "syllabus. Counted from verified syllabus inclusion records, never from book headings.",
    "content_completed": "Published lessons you marked completed ÷ published lessons in your class and subjects. "
    "This is what you have studied, not what you know.",
    "demonstrated_knowledge": "Topics where your recent independent answers meet the evidence rules "
    "(evidence_rules_v2) ÷ topics in your class and subjects' books.",
}
NO_PROFILE = "Choose your class and subjects to see this."


def _meter(key: str, num: int | None, den: int | None, unavailable: str | None) -> dict[str, Any]:
    if unavailable is not None or num is None or not den:
        return {"key": key, "definition": DEFINITIONS[key], "numerator": None, "denominator": None, "percent": None,
                "unavailable": unavailable or "Not enough information yet."}  # fmt: skip
    return {
        "key": key,
        "definition": DEFINITIONS[key],
        "numerator": num,
        "denominator": den,
        "percent": round(100 * num / den, 1),
        "unavailable": None,
    }


def _meters(
    db: Session, user_id: uuid.UUID, chapters: list[Any], now: datetime, exams: list[str], year: int | None
) -> list[dict[str, Any]]:
    from portal_api.modules.assessment import evidence
    from portal_api.modules.content import completion
    from portal_api.modules.content.models import Availability, ContentItem
    from portal_api.modules.curriculum.models import Topic

    coverage = _meter(
        "syllabus_coverage",
        None,
        None,
        "The syllabus for your exams hasn't been verified yet.",  # P05.S2 inclusion records, B02
    )
    if not chapters:
        return [
            coverage,
            _meter("content_completed", None, None, NO_PROFILE),
            _meter("demonstrated_knowledge", None, None, NO_PROFILE),
        ]
    ids = [c.id for c in chapters]
    topics = set(db.scalars(select(Topic.id).where(Topic.chapter_id.in_(ids), Topic.retired_at.is_(None))))
    coverage = _syllabus(db, topics, exams, year) or coverage
    live = set(
        db.scalars(
            select(ContentItem.id).where(
                ContentItem.kind == "lesson",
                ContentItem.availability == Availability.live.value,
                ContentItem.chapter_id.in_(ids),
            )
        )
    )
    done = completion.completed_in(db, user_id, ids) & live
    results = evidence.classify(evidence.learner_responses(db, user_id, now), now)
    states = [r.state for t in topics if (r := results.get(t)) is not None]
    shown = states.count("demonstrated")
    # Cold start: until some topic has enough evidence to classify, a percentage would only be an invented zero.
    classified = any(s != "insufficient_evidence" for s in states)
    why = (
        None
        if topics and classified
        else "Not enough evidence yet: answer practice questions on different topics to see this."
        if topics
        else "No topics are listed for your books."
    )
    return [
        coverage,
        _meter(
            "content_completed", len(done), len(live), None if live else "No published lessons in your subjects yet."
        ),
        _meter("demonstrated_knowledge", shown, len(topics), why),
    ]


def _syllabus(db: Session, topics: set[uuid.UUID], exams: list[str], year: int | None) -> dict[str, Any] | None:
    """INCLUSION-01: syllabus coverage from verified inclusion records for the learner's exam (else the board syllabus)
    and year. None (the meter stays unavailable) until such records exist."""
    from portal_api.modules.content import inclusion

    if year is None:
        return None
    counts = inclusion.syllabus_counts(db, topics, exams[0] if exams else "board_syllabus", year)
    return _meter("syllabus_coverage", counts[0], counts[1], None) if counts else None


def _continue(db: Session, user_id: uuid.UUID, grade: int | None) -> dict[str, Any] | None:
    """The most recently opened live lesson (in the profile's class) that isn't marked completed."""
    from portal_api.modules.analytics.events import AnalyticsEvent
    from portal_api.modules.content.completion import LessonCompletion
    from portal_api.modules.content.models import Availability, ContentItem
    from portal_api.modules.curriculum.models import Chapter

    lesson = AnalyticsEvent.properties["lesson_id"].astext
    opened = (
        select(lesson.label("lesson_id"), func.max(AnalyticsEvent.occurred_at).label("at"))
        .where(AnalyticsEvent.user_id == user_id, AnalyticsEvent.name == "lesson.started")
        .group_by(lesson)
        .subquery()
    )
    done = select(LessonCompletion.item_id).where(LessonCompletion.user_id == user_id)
    stmt = (
        select(ContentItem, Chapter, opened.c.at)
        .join(opened, opened.c.lesson_id == cast(ContentItem.id, String))
        .join(Chapter, Chapter.id == ContentItem.chapter_id)
        .where(
            ContentItem.kind == "lesson",
            ContentItem.availability == Availability.live.value,
            ContentItem.id.not_in(done),
        )
        .order_by(opened.c.at.desc())
        .limit(1)
    )
    if grade is not None:
        stmt = stmt.where(ContentItem.grade_number == grade)
    row = db.execute(stmt).first()
    if row is None:
        return None
    item, chapter, at = row
    return {
        "lesson_id": item.id,
        "title": item.title,
        "grade": item.grade_number,
        "subject": item.subject_code,
        "chapter_id": chapter.id,
        "chapter_number": chapter.number,
        "chapter_title": chapter.title,
        "opened_at": at,
    }


def _revision(db: Session, user_id: uuid.UUID, now: datetime) -> dict[str, int]:
    from portal_api.modules.assessment.notebook import MistakeEntry

    open_ = MistakeEntry.user_id == user_id, MistakeEntry.status == "open"
    return {
        "due": int(db.scalar(select(func.count()).where(*open_, MistakeEntry.due_at <= now)) or 0),
        "open": int(db.scalar(select(func.count()).where(*open_)) or 0),
    }


def build(db: Session, user_id: uuid.UUID) -> dict[str, Any]:
    from portal_api.modules.assessment import progress
    from portal_api.modules.identity.models import StudentProfile

    report = progress.report(db, user_id)  # also syncs the notebook, so the revision counts below are current
    now: datetime = db.execute(select(func.now())).scalar_one()
    p = db.get(StudentProfile, user_id)
    grade = p.grade if p is not None and p.subjects else None  # one class only: XI and XII are never mixed
    subjects = list(p.subjects) if p is not None and grade else []
    chapters = [c for s in subjects for c in forms._book_chapters(db, grade, s)] if grade else []
    return {
        "generated_at": now,
        "profile": {"grade": grade, "subjects": subjects} if grade else None,
        "meters": _meters(
            db, user_id, chapters, now, list(p.target_exams or []) if p else [], p.target_year if p else None
        ),
        "continue_learning": _continue(db, user_id, grade),
        "revision": _revision(db, user_id, now),
        "recent": report["recent"][:3],
        "results_pending": report["results_pending"],
    }
