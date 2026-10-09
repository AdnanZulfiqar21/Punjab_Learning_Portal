"""Academic overview (roadmap P16.S1.T2; ACADEMIC-OVERVIEW-01).

Per chapter of one class and subject:

* what learners can use now: live lessons, live MCQ families and live written questions;
* the editorial pipeline: drafts, items in review and approved items waiting for publication;
* problems: quarantined items and open academic error reports;
* MCQ pool sufficiency against the D06 rule (at least `POOL_RULE` approved unique families). Quarantined questions
  never count, so a chapter below the rule cannot honestly offer a full chapter test.

Counts only. No learner identities and no question content.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from portal_api.errors import NotFound
from portal_api.modules.content.models import Availability, ContentItem, ItemState
from portal_api.modules.curriculum.models import BookEdition, Chapter, Grade, Subject

POOL_RULE = 3  # D06 proposed default: approved unique families per blueprint slot


def overview(db: Session, grade: int, subject: str) -> dict[str, Any]:
    from portal_api.modules.support.models import SupportTicket

    book = db.scalar(
        select(BookEdition)
        .join(Grade, Grade.id == BookEdition.grade_id)
        .join(Subject, Subject.id == BookEdition.subject_id)
        .where(Grade.number == grade, Subject.code == subject)
    )
    if book is None:
        raise NotFound("No book for that class and subject.")
    chapters = list(
        db.scalars(
            select(Chapter)
            .where(Chapter.book_id == book.id, Chapter.retired_at.is_(None))
            .order_by(Chapter.display_order)
        )
    )
    ids = [c.id for c in chapters]

    def grouped(*where: Any, distinct_family: bool = False) -> dict[Any, int]:
        counted = (
            func.count(func.distinct(func.coalesce(ContentItem.family_id, ContentItem.id)))
            if distinct_family
            else func.count()
        )
        rows = db.execute(
            select(ContentItem.chapter_id, counted)
            .where(ContentItem.chapter_id.in_(ids), *where)
            .group_by(ContentItem.chapter_id)
        ).all()
        return {c: int(n) for c, n in rows}

    live = ContentItem.availability == Availability.live.value
    lessons = grouped(ContentItem.kind == "lesson", live)
    mcq_families = grouped(ContentItem.kind == "mcq", live, distinct_family=True)
    written = grouped(ContentItem.kind == "written", live)
    drafts = grouped(ContentItem.state.in_((ItemState.draft.value, ItemState.changes_requested.value)))
    in_review = grouped(ContentItem.state == ItemState.submitted.value)
    approved = grouped(ContentItem.state == ItemState.approved.value)
    quarantined = grouped(ContentItem.availability == Availability.quarantined.value)
    reports = dict(
        db.execute(
            select(ContentItem.chapter_id, func.count())
            .join(SupportTicket, SupportTicket.content_item_id == ContentItem.id)
            .where(
                ContentItem.chapter_id.in_(ids),
                SupportTicket.category == "academic_report",
                SupportTicket.status != "resolved",
            )
            .group_by(ContentItem.chapter_id)
        ).all()
    )
    rows: list[dict[str, Any]] = []
    for c in chapters:
        fam = mcq_families.get(c.id, 0)
        rows.append(
            {
                "chapter_id": str(c.id),
                "key": c.natural_key,
                "number": c.number,
                "title": c.title,
                "live_lessons": lessons.get(c.id, 0),
                "live_mcq_families": fam,
                "live_written": written.get(c.id, 0),
                "drafts": drafts.get(c.id, 0),
                "in_review": in_review.get(c.id, 0),
                "approved_unpublished": approved.get(c.id, 0),
                "quarantined": quarantined.get(c.id, 0),
                "open_reports": int(reports.get(c.id, 0)),
                "pool_sufficient": fam >= POOL_RULE,
            }
        )
    totals = {
        k: sum(r[k] for r in rows)
        for k in (
            "live_lessons",
            "live_mcq_families",
            "live_written",
            "drafts",
            "in_review",
            "approved_unpublished",
            "quarantined",
            "open_reports",
        )
    }
    return {
        "grade": grade,
        "subject": subject,
        "pool_rule": POOL_RULE,
        "chapters": rows,
        "totals": totals,
        "chapters_with_lessons": sum(1 for r in rows if r["live_lessons"]),
        "chapters_pool_sufficient": sum(1 for r in rows if r["pool_sufficient"]),
    }
