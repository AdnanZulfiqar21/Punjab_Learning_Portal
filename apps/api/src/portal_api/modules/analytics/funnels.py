"""Funnel and retention report (roadmap P16.S2.T2; FUNNEL-01), built from the analytics events (ANALYTICS-EVENTS-01).

Cohorts are learners (test accounts and staff excluded) grouped by the ISO week their account was created; each cohort
states its age. Steps, each counted once per learner (events are deduplicated by their stable IDs):

* **first lesson**: a `lesson.started` event;
* **first completed test**: an `attempt.submitted` event;
* **repeat study**: learning activity (either event) on at least two different days within `REPEAT_DAYS` days of the
  learner's first activity;
* **paid conversion**: unavailable until payments exist (B06).

A cohort younger than a step's window is marked `too_early` for that step instead of being read as drop-off. Events
only exist from the moment collection started (`events_since`), so earlier activity is missing: the report says so.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import and_, distinct, exists, func, select
from sqlalchemy.orm import Session

from portal_api.db import get_session
from portal_api.modules.identity.deps import Principal, require
from portal_api.modules.identity.permissions import Permission

REPORT_VERSION = 1
REPEAT_DAYS = 14
WEEKS = 12
LEARNING = ("lesson.started", "attempt.submitted")


def report(db: Session) -> dict[str, Any]:
    from portal_api.config import get_settings
    from portal_api.modules.analytics.events import AnalyticsEvent
    from portal_api.modules.identity.models import AppUser, StaffRoleGrant

    now: datetime = db.execute(select(func.now())).scalar_one()
    staff = exists().where(StaffRoleGrant.user_id == AppUser.id, StaffRoleGrant.revoked_at.is_(None))
    learner = and_(AppUser.status == "active", ~staff, AppUser.issuer != get_settings().dev_auth_issuer)
    week = func.date_trunc("week", AppUser.created_at)
    since = now - timedelta(weeks=WEEKS)

    def first(name: str) -> Any:
        return (
            select(AnalyticsEvent.user_id, func.min(AnalyticsEvent.occurred_at).label("at"))
            .where(AnalyticsEvent.name == name)
            .group_by(AnalyticsEvent.user_id)
            .subquery()
        )

    lesson, test = first("lesson.started"), first("attempt.submitted")
    activity = (
        select(AnalyticsEvent.user_id, func.date_trunc("day", AnalyticsEvent.occurred_at).label("day"))
        .where(AnalyticsEvent.name.in_(LEARNING))
        .distinct()
        .subquery()
    )
    first_day = select(activity.c.user_id, func.min(activity.c.day).label("d")).group_by(activity.c.user_id).subquery()
    repeat = (
        select(activity.c.user_id)
        .join(first_day, first_day.c.user_id == activity.c.user_id)
        .where(activity.c.day > first_day.c.d, activity.c.day <= first_day.c.d + timedelta(days=REPEAT_DAYS))
        .distinct()
        .subquery()
    )
    rows = db.execute(
        select(
            week.label("week"),
            func.count(distinct(AppUser.id)),
            func.count(distinct(lesson.c.user_id)),
            func.count(distinct(test.c.user_id)),
            func.count(distinct(repeat.c.user_id)),
        )
        .outerjoin(lesson, lesson.c.user_id == AppUser.id)
        .outerjoin(test, test.c.user_id == AppUser.id)
        .outerjoin(repeat, repeat.c.user_id == AppUser.id)
        .where(learner, AppUser.created_at >= since)
        .group_by(week)
        .order_by(week.desc())
    ).all()
    cohorts = []
    for w, signed_up, lessons, tests, repeats in rows:
        age_days = max(0, (now - w).days)
        cohorts.append(
            {
                "week_start": w.date().isoformat(),
                "age_days": age_days,
                "signed_up": int(signed_up),
                "first_lesson": int(lessons),
                "first_completed_test": int(tests),
                "repeat_study": int(repeats),
                "repeat_study_too_early": age_days < REPEAT_DAYS,
                "paid_conversion": {"value": None, "available": False, "blocker": "B06"},
            }
        )
    events_since = db.scalar(select(func.min(AnalyticsEvent.occurred_at)))
    return {
        "report_version": REPORT_VERSION,
        "generated_at": now,
        "events_since": events_since,
        "repeat_days": REPEAT_DAYS,
        "cohorts": cohorts,
        "definitions": {
            "cohort": "Learners (no staff role, no test accounts) by the ISO week their account was created.",
            "first_lesson": "Opened a published lesson at least once (lesson.started).",
            "first_completed_test": "Submitted at least one test (attempt.submitted).",
            "repeat_study": f"Learned on two or more different days within {REPEAT_DAYS} days of first activity. "
            "Cohorts younger than that are marked too early, not counted as drop-off.",
            "paid_conversion": "Unavailable until payments exist (B06).",
            "coverage": "Events exist only since collection started (events_since); earlier activity is not counted.",
        },
    }


# ------------------------------------------------------------------ route
router = APIRouter(prefix="/v1/admin/analytics", tags=["analytics"])
Viewer = Annotated[Principal, Depends(require(Permission.view_business_overview))]


class PaidConversion(BaseModel):
    value: int | None
    available: bool
    blocker: str


class FunnelCohort(BaseModel):
    week_start: str
    age_days: int
    signed_up: int
    first_lesson: int
    first_completed_test: int
    repeat_study: int
    repeat_study_too_early: bool
    paid_conversion: PaidConversion


class FunnelReport(BaseModel):
    report_version: int
    generated_at: datetime
    events_since: datetime | None
    repeat_days: int
    cohorts: list[FunnelCohort]
    definitions: dict[str, str]


@router.get("/funnel", response_model=FunnelReport, summary="Learning funnel and repeat study by cohort (MFA)")
def funnel(db: Annotated[Session, Depends(get_session)], who: Viewer, response: Response) -> FunnelReport:
    response.headers["Cache-Control"] = "private, no-store"
    return FunnelReport(**report(db))
