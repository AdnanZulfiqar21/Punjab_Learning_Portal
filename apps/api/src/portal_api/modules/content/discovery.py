"""Course discovery (roadmap P11.S1.T3; DISCOVERY-01).

What a visitor can actually study, per book: live reviewed lessons (one per concept, whatever its languages), free
previews and practice question families, counted only from published content (drafts, quarantined and retired items
never count). A book with nothing published says so (`not_yet_published`) instead of looking empty or "coming soon".
Filters: class, track, subject, published exam pattern and availability. Class XI and XII are listed separately and
never merged.

Tracks come from the launch manifest (docs/project/LAUNCH_MANIFEST.md, "Tracks"): Pre-Medical = Biology, Chemistry,
Physics; Pre-Engineering = Mathematics, Chemistry, Physics; ICS = combinations within the five active subjects
(Computer Science, Mathematics, Physics here). *Provisional:* the ICS combination shown is the in-scope one; other ICS
combinations (Statistics, Economics) are outside SCOPE-01. Plans and bundles are not offered yet (P14.S1.T1), so no
bundle contents are shown.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from portal_api.days import local_date
from portal_api.db import get_session
from portal_api.errors import NotFound
from portal_api.modules.content.models import Availability, ContentItem
from portal_api.modules.curriculum.editions import covers

TRACKS: dict[str, tuple[str, tuple[str, ...], str]] = {
    "pre_medical": ("Pre-Medical", ("biology", "chemistry", "physics"), ""),
    "pre_engineering": ("Pre-Engineering", ("mathematics", "chemistry", "physics"), ""),
    "ics": (
        "ICS",
        ("computer_science", "mathematics", "physics"),
        "ICS combinations vary; the portal covers Computer Science, Mathematics and Physics.",
    ),
}
PREVIEWS_SHOWN = 30
Track = Literal["pre_medical", "pre_engineering", "ics"]
AvailabilityFilter = Literal["all", "lessons", "previews", "practice"]


def _state(live: int, practice: int) -> str:
    return "lessons" if live else "practice_only" if practice else "not_yet_published"


def discover(
    db: Session,
    *,
    grade: int | None,
    track: str | None,
    subject: str | None,
    exam: str | None,
    availability: str,
) -> dict[str, Any]:
    from portal_api.modules.assessment import profiles
    from portal_api.modules.curriculum.models import BookEdition, Chapter, Grade, Subject

    published = profiles.published(db)
    today = local_date(db.execute(select(func.now())).scalar_one())
    exam_scope: set[tuple[int, str]] | None = None
    if exam is not None:
        match = next(((p, v) for p, v in published if p.code == exam), None)
        if match is None:
            raise NotFound("No published exam pattern has that code.")
        exam_scope = {(g, s["subject"]) for s in match[1].rules.get("sections", []) for g in s.get("grades", [])}

    books = db.execute(
        select(BookEdition, Grade, Subject)
        .join(Grade, Grade.id == BookEdition.grade_id)
        .join(Subject, Subject.id == BookEdition.subject_id)
        .where(Subject.active)
        .order_by(Grade.number, Subject.display_order)
    ).all()
    chapters = db.execute(select(Chapter.id, Chapter.book_id, Chapter.number).where(Chapter.retired_at.is_(None))).all()
    book_of = {cid: bid for cid, bid, _ in chapters}
    number_of = {cid: n for cid, _, n in chapters}
    chapter_count: dict[uuid.UUID, int] = {}
    for _, bid, _ in chapters:
        chapter_count[bid] = chapter_count.get(bid, 0) + 1

    live = ContentItem.availability == Availability.live.value
    # Language variants of one lesson concept (LESSON-VARIANTS-01) count once; English is preferred for the title.
    rows = db.execute(
        select(
            ContentItem.id,
            ContentItem.chapter_id,
            ContentItem.access_tier,
            ContentItem.title,
            func.coalesce(ContentItem.concept_id, ContentItem.id),
            ContentItem.language,
        ).where(ContentItem.kind == "lesson", live)
    ).all()
    concepts: dict[uuid.UUID, list[Any]] = {}
    for lid, cid, tier, title, concept, _ in sorted(rows, key=lambda r: r[5] != "en"):
        entry = concepts.setdefault(concept, [lid, cid, "premium", title])
        if tier == "preview":
            entry[2] = "preview"
    lessons = [tuple(e) for e in concepts.values()]
    families = db.execute(
        select(ContentItem.chapter_id, func.count(func.distinct(func.coalesce(ContentItem.family_id, ContentItem.id))))
        .where(ContentItem.kind == "mcq", live, ContentItem.question_pool == "practice")
        .group_by(ContentItem.chapter_id)
    ).all()

    per_book: dict[uuid.UUID, dict[str, Any]] = {}
    for book_id in {b.id for b, _, _ in books}:
        per_book[book_id] = {"live": 0, "previews": 0, "practice": 0, "chapters": set()}
    for _, cid, tier, _ in lessons:
        owner = book_of.get(cid)
        if owner is not None and owner in per_book:
            per_book[owner]["live"] += 1
            per_book[owner]["previews"] += 1 if tier == "preview" else 0
            per_book[owner]["chapters"].add(cid)
    for cid, n in families:
        owner = book_of.get(cid)
        if owner is not None and owner in per_book:
            per_book[owner]["practice"] += int(n)

    wanted_subjects = set(TRACKS[track][1]) if track else None
    out_books, kept = [], set()
    for b, g, s in books:
        if not covers(b.effective_from, b.effective_until, today):
            continue
        if grade is not None and g.number != grade:
            continue
        if subject is not None and s.code != subject:
            continue
        if wanted_subjects is not None and s.code not in wanted_subjects:
            continue
        if exam_scope is not None and (g.number, s.code) not in exam_scope:
            continue
        counts = per_book[b.id]
        row = {
            "book_id": b.id,
            "grade": g.number,
            "subject": s.code,
            "subject_name": s.name,
            "chapter_label": b.chapter_label,
            "chapter_count": chapter_count.get(b.id, 0),
            "completeness": b.source.completeness,
            "chapters_with_lessons": len(counts["chapters"]),
            "live_lessons": counts["live"],
            "preview_lessons": counts["previews"],
            "practice_questions": counts["practice"],
            "state": _state(counts["live"], counts["practice"]),
        }
        if availability == "lessons" and not row["live_lessons"]:
            continue
        if availability == "previews" and not row["preview_lessons"]:
            continue
        if availability == "practice" and not row["practice_questions"]:
            continue
        out_books.append(row)
        kept.add(b.id)

    subject_of = {b.id: (g.number, s.code, s.name) for b, g, s in books}
    previews = []
    for lid, cid, tier, title in sorted(lessons, key=lambda x: (number_of.get(x[1], 0), x[3])):
        owner = book_of.get(cid)
        if tier != "preview" or owner is None or owner not in kept:
            continue
        grade_no, code, name = subject_of[owner]
        previews.append(
            {
                "lesson_id": lid,
                "title": title,
                "grade": grade_no,
                "subject": code,
                "subject_name": name,
                "chapter_id": cid,
                "chapter_number": number_of.get(cid, 0),
            }
        )
    return {
        "tracks": [
            {"code": code, "name": name, "subjects": list(subs), "note": note}
            for code, (name, subs, note) in TRACKS.items()
        ],
        "exams": [
            {
                "code": p.code,
                "name": p.name,
                "year": v.year,
                "subjects": sorted({s["subject"] for s in v.rules.get("sections", [])}),
            }
            for p, v in published
        ],
        "books": out_books,
        "previews": previews[:PREVIEWS_SHOWN],
        "plans_note": "Plans and bundles aren't on sale yet. Free previews are open to everyone, and the free trial "
        "opens the rest of what is published.",
    }


# ------------------------------------------------------------------ routes
router = APIRouter(prefix="/v1", tags=["discovery"])
DB = Annotated[Session, Depends(get_session)]


class TrackOut(BaseModel):
    code: str
    name: str
    subjects: list[str]
    note: str


class ExamOut(BaseModel):
    code: str
    name: str
    year: int
    subjects: list[str]


class BookAvailability(BaseModel):
    book_id: uuid.UUID
    grade: int
    subject: str
    subject_name: str
    chapter_label: str
    chapter_count: int
    completeness: str
    chapters_with_lessons: int
    live_lessons: int
    preview_lessons: int
    practice_questions: int
    state: Literal["lessons", "practice_only", "not_yet_published"]


class PreviewLesson(BaseModel):
    lesson_id: uuid.UUID
    title: str
    grade: int
    subject: str
    subject_name: str
    chapter_id: uuid.UUID
    chapter_number: int


class DiscoveryOut(BaseModel):
    tracks: list[TrackOut]
    exams: list[ExamOut]
    books: list[BookAvailability]
    previews: list[PreviewLesson]
    plans_note: str


@router.get("/discovery", response_model=DiscoveryOut, summary="What is published per book, with filters (public)")
def discovery(
    db: DB,
    response: Response,
    grade: Annotated[int | None, Query(ge=11, le=12)] = None,
    track: Track | None = None,
    subject: Annotated[str | None, Query(min_length=2, max_length=40)] = None,
    exam: Annotated[str | None, Query(min_length=2, max_length=40)] = None,
    availability: AvailabilityFilter = "all",
) -> DiscoveryOut:
    response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=300"
    return DiscoveryOut(**discover(db, grade=grade, track=track, subject=subject, exam=exam, availability=availability))
