"""Learning outcomes alongside engagement (roadmap P16.S2.T3; LEARNING-REPORT-01).

For one class and subject, side by side and never blended into one score:

* **Demonstrated knowledge** (outcome): for the most recently active learners in this book (at most `SAMPLE`, the
  sample size is stated), the share of the book's topics each has demonstrated under `evidence_rules_v2`, reported as
  a distribution and a median. Learners with no answers in the window are not assessed, so they are not counted as 0.
* **Content completed** (engagement): lessons marked complete in this book against the live lessons, per learner who
  completed any.
* **Lesson visits** (engagement): distinct learner-days with a `lesson.started` event in this book in the last 30 days.
* **Syllabus coverage** is unavailable until verified exam outcomes are mapped (B02); **watch time** until video exists
  (B05).

Engagement and outcomes moving together is not evidence that one causes the other: any such reading is a hypothesis
until it is properly evaluated, and the report says so.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, exists, func, select
from sqlalchemy.orm import Session

from portal_api.db import get_session
from portal_api.modules.identity.deps import Principal, require
from portal_api.modules.identity.permissions import Permission

REPORT_VERSION = 1
SAMPLE = 200
BUCKETS = ((0, 0), (0, 25), (25, 50), (50, 75), (75, 100))  # exactly 0, then (from, to] percent


def _bucket(share: float) -> tuple[int, int]:
    if share == 0:
        return BUCKETS[0]
    return next(b for b in BUCKETS[1:] if share <= b[1])


NOTE = (
    "Outcomes and engagement are shown side by side. If they move together, that is a hypothesis to evaluate, "
    "not evidence that one causes the other."
)


def report(db: Session, grade: int, subject: str) -> dict[str, Any]:
    from portal_api.config import get_settings
    from portal_api.errors import NotFound
    from portal_api.modules.analytics.events import AnalyticsEvent
    from portal_api.modules.assessment import evidence, forms
    from portal_api.modules.assessment.models import Attempt, FormItem
    from portal_api.modules.content.completion import LessonCompletion
    from portal_api.modules.content.models import Availability, ContentItem
    from portal_api.modules.curriculum.models import Topic
    from portal_api.modules.identity.models import AppUser, StaffRoleGrant

    now: datetime = db.execute(select(func.now())).scalar_one()
    chapters = forms._book_chapters(db, grade, subject)
    if not chapters:
        raise NotFound("No book is available for this class and subject.")
    chapter_ids = [c.id for c in chapters]
    topics = set(db.scalars(select(Topic.id).where(Topic.chapter_id.in_(chapter_ids), Topic.retired_at.is_(None))))
    staff = exists().where(StaffRoleGrant.user_id == AppUser.id, StaffRoleGrant.revoked_at.is_(None))
    learner = and_(AppUser.status == "active", ~staff, AppUser.issuer != get_settings().dev_auth_issuer)
    window = now - evidence.WINDOW
    recent = (
        select(Attempt.user_id, func.max(Attempt.finalised_at).label("last"))
        .join(FormItem, FormItem.form_id == Attempt.form_id)
        .where(
            Attempt.status == "finalised",
            Attempt.finalised_at >= window,
            FormItem.grade_number == grade,
            FormItem.subject_code == subject,
        )
        .group_by(Attempt.user_id)
        .subquery()
    )
    sample = list(
        db.scalars(
            select(recent.c.user_id)
            .join(AppUser, AppUser.id == recent.c.user_id)
            .where(learner)
            .order_by(recent.c.last.desc())
            .limit(SAMPLE)
        )
    )
    shares: list[float] = []
    for uid in sample:
        results = evidence.classify(evidence.learner_responses(db, uid, now), now)
        if not topics:
            continue
        shown = sum(1 for t in topics if (r := results.get(t)) is not None and r.state == "demonstrated")
        shares.append(100 * shown / len(topics))
    buckets = [
        {"from": lo, "to": hi, "learners": sum(1 for x in shares if _bucket(x) == (lo, hi))} for lo, hi in BUCKETS
    ]
    live = int(
        db.scalar(
            select(func.count(ContentItem.id)).where(
                ContentItem.kind == "lesson",
                ContentItem.availability == Availability.live.value,
                ContentItem.chapter_id.in_(chapter_ids),
            )
        )
        or 0
    )
    learner_ids = select(AppUser.id).where(learner)
    per_learner = db.execute(
        select(LessonCompletion.user_id, func.count(LessonCompletion.id))
        .join(ContentItem, ContentItem.id == LessonCompletion.item_id)
        .where(
            ContentItem.chapter_id.in_(chapter_ids),
            ContentItem.availability == Availability.live.value,
            LessonCompletion.user_id.in_(learner_ids),
        )
        .group_by(LessonCompletion.user_id)
    ).all()
    lesson_ids = [
        str(i)
        for i in db.scalars(
            select(ContentItem.id).where(ContentItem.kind == "lesson", ContentItem.chapter_id.in_(chapter_ids))
        )
    ]
    day = func.date_trunc("day", AnalyticsEvent.occurred_at)
    visits = (
        int(
            db.scalar(
                select(func.count()).select_from(
                    select(AnalyticsEvent.user_id, day)
                    .where(
                        AnalyticsEvent.name == "lesson.started",
                        AnalyticsEvent.occurred_at >= now - timedelta(days=30),
                        AnalyticsEvent.properties["lesson_id"].astext.in_(lesson_ids),
                        AnalyticsEvent.user_id.in_(learner_ids),
                    )
                    .distinct()
                    .subquery()
                )
            )
            or 0
        )
        if lesson_ids
        else 0
    )
    return {
        "report_version": REPORT_VERSION,
        "generated_at": now,
        "grade": grade,
        "subject": subject,
        "outcomes": {
            "rules_version": evidence.RULES_VERSION,
            "learners_assessed": len(shares),
            "sample_limit": SAMPLE,
            "topics_in_book": len(topics),
            "median_demonstrated_pct": round(statistics.median(shares), 1) if shares else None,
            "distribution": buckets,
        },
        "engagement": {
            "live_lessons": live,
            "learners_completing": len(per_learner),
            "median_completed_pct": round(statistics.median([100 * n / live for _, n in per_learner]), 1)
            if per_learner and live
            else None,
            "lesson_visit_days_30d": visits,
        },
        "unavailable": {"syllabus_coverage": "B02", "watch_time": "B05"},
        "note": NOTE,
    }


# ------------------------------------------------------------------ route
router = APIRouter(prefix="/v1/admin/analytics", tags=["analytics"])
Viewer = Annotated[Principal, Depends(require(Permission.view_business_overview))]


class Bucket(BaseModel):
    from_pct: int = Field(alias="from")
    to_pct: int = Field(alias="to")
    learners: int


class Outcomes(BaseModel):
    rules_version: str
    learners_assessed: int
    sample_limit: int
    topics_in_book: int
    median_demonstrated_pct: float | None
    distribution: list[Bucket]


class Engagement(BaseModel):
    live_lessons: int
    learners_completing: int
    median_completed_pct: float | None
    lesson_visit_days_30d: int


class LearningReport(BaseModel):
    report_version: int
    generated_at: datetime
    grade: int
    subject: str
    outcomes: Outcomes
    engagement: Engagement
    unavailable: dict[str, str]
    note: str


@router.get("/learning", response_model=LearningReport, summary="Learning outcomes beside engagement, one book (MFA)")
def learning(
    db: Annotated[Session, Depends(get_session)],
    who: Viewer,
    response: Response,
    grade: Annotated[int, Query(ge=11, le=12)],
    subject: Annotated[str, Query(min_length=2, max_length=40)],
) -> LearningReport:
    response.headers["Cache-Control"] = "private, no-store"
    return LearningReport.model_validate(report(db, grade, subject))
