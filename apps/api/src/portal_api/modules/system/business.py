"""Business overview (roadmap P16.S1.T1; BUSINESS-OVERVIEW-01).

Aggregate counts only: no names, emails or per-person rows. Every figure has a written definition (`DEFINITIONS`).

* **Learners** are accounts with no active staff role. Accounts from the development identity adapter are counted
  separately as test accounts and excluded from every learner figure, so fixtures never inflate the numbers.
* **Purchases and refunds** come from `paid` entitlements and `refunded` entitlement status. No payment provider is
  connected yet (B06), so these stay zero and are labelled unavailable rather than estimated; revenue is never shown
  until verified payments exist, and then only from provider-confirmed payments.
* **Trial cohorts** group trials by the ISO week they started. A cohort whose trials haven't ended yet is reported as
  still open, never as non-conversion.
* **Content usage** counts real learner activity in the last 30 days.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import and_, distinct, exists, func, select, union
from sqlalchemy.orm import Session

from portal_api.db import get_session
from portal_api.modules.identity.deps import Principal, require
from portal_api.modules.identity.permissions import Permission

REPORT_VERSION = 1
SOURCES = ("trial", "paid", "scholarship", "promotional", "pilot")
DEFINITIONS = {
    "learners": "Active accounts with no active staff role, excluding test accounts.",
    "active_7d": "Learners seen in the last 7 days.",
    "active_30d": "Learners seen in the last 30 days.",
    "test_accounts": "Accounts from the development identity adapter; excluded from every other figure.",
    "entitlements_active": "Learners with access now, by source (trial, paid, scholarship, promotional, pilot).",
    "verified_purchases": "Paid entitlements from provider-confirmed payments. Unavailable until payments exist (B06).",
    "refunds": "Paid entitlements later refunded. Unavailable until payments exist (B06).",
    "trial_cohorts": "Trials by ISO start week: started, still running, ended, converted to paid. Open cohorts are not "
    "counted as non-conversion.",
    "content_usage_30d": "Last 30 days: lessons marked complete, practice/mock/review tests submitted, written tests "
    "sealed, and distinct learners doing any of these.",
}


def report(db: Session) -> dict[str, Any]:
    from portal_api.config import get_settings
    from portal_api.modules.access.models import Entitlement, TrialGrant
    from portal_api.modules.assessment.models import Attempt
    from portal_api.modules.content.completion import LessonCompletion
    from portal_api.modules.identity.models import AppUser, StaffRoleGrant
    from portal_api.modules.written.models import WrittenAttempt

    now: datetime = db.execute(select(func.now())).scalar_one()
    dev_issuer = get_settings().dev_auth_issuer
    staff = exists().where(StaffRoleGrant.user_id == AppUser.id, StaffRoleGrant.revoked_at.is_(None))
    learner = and_(AppUser.status == "active", ~staff, AppUser.issuer != dev_issuer)
    learner_ids = select(AppUser.id).where(learner)

    def count(*where: Any) -> int:
        return int(db.scalar(select(func.count(AppUser.id)).where(learner, *where)) or 0)

    test_accounts = int(db.scalar(select(func.count(AppUser.id)).where(AppUser.issuer == dev_issuer)) or 0)
    by_source = dict(
        db.execute(
            select(Entitlement.source, func.count(distinct(Entitlement.user_id)))
            .where(
                Entitlement.status == "active",
                Entitlement.starts_at <= now,
                Entitlement.ends_at > now,
                Entitlement.user_id.in_(learner_ids),
            )
            .group_by(Entitlement.source)
        ).all()
    )
    paid = int(
        db.scalar(
            select(func.count(Entitlement.id)).where(Entitlement.source == "paid", Entitlement.user_id.in_(learner_ids))
        )
        or 0
    )
    refunded = int(
        db.scalar(
            select(func.count(Entitlement.id)).where(
                Entitlement.source == "paid", Entitlement.status == "refunded", Entitlement.user_id.in_(learner_ids)
            )
        )
        or 0
    )
    week = func.date_trunc("week", TrialGrant.granted_at)
    converted = exists().where(
        Entitlement.user_id == TrialGrant.user_id,
        Entitlement.source == "paid",
        Entitlement.starts_at >= TrialGrant.granted_at,
    )
    cohorts = [
        {
            "week_start": w.date().isoformat(),
            "started": int(started),
            "running": int(running),
            "ended": int(started) - int(running),
            "converted_to_paid": int(conv),
            "open": bool(running),
        }
        for w, started, running, conv in db.execute(
            select(
                week,
                func.count(TrialGrant.id),
                func.count(TrialGrant.id).filter(TrialGrant.ends_at > now),
                func.count(TrialGrant.id).filter(converted),
            )
            .where(TrialGrant.user_id.in_(learner_ids), TrialGrant.granted_at >= now - timedelta(weeks=12))
            .group_by(week)
            .order_by(week.desc())
        ).all()
    ]
    since = now - timedelta(days=30)
    completions = int(
        db.scalar(
            select(func.count(LessonCompletion.id)).where(
                LessonCompletion.completed_at >= since, LessonCompletion.user_id.in_(learner_ids)
            )
        )
        or 0
    )
    tests = int(
        db.scalar(
            select(func.count(Attempt.id)).where(
                Attempt.status == "finalised", Attempt.finalised_at >= since, Attempt.user_id.in_(learner_ids)
            )
        )
        or 0
    )
    written = int(
        db.scalar(
            select(func.count(WrittenAttempt.id)).where(
                WrittenAttempt.sealed_at >= since, WrittenAttempt.user_id.in_(learner_ids)
            )
        )
        or 0
    )
    active_users = union(
        select(LessonCompletion.user_id).where(LessonCompletion.completed_at >= since),
        select(Attempt.user_id).where(Attempt.status == "finalised", Attempt.finalised_at >= since),
        select(WrittenAttempt.user_id).where(WrittenAttempt.sealed_at >= since),
    ).subquery()
    engaged = int(
        db.scalar(select(func.count()).select_from(active_users).where(active_users.c.user_id.in_(learner_ids))) or 0
    )
    return {
        "report_version": REPORT_VERSION,
        "generated_at": now,
        "definitions": DEFINITIONS,
        "learners": count(),
        "active_7d": count(AppUser.last_seen_at >= now - timedelta(days=7)),
        "active_30d": count(AppUser.last_seen_at >= since),
        "test_accounts": test_accounts,
        "entitlements_active": {
            s: int(by_source.get(s, 0)) for s in ("trial", "paid", "scholarship", "promotional", "pilot")
        },
        "verified_purchases": {"value": paid, "available": False, "blocker": "B06"},
        "refunds": {"value": refunded, "available": False, "blocker": "B06"},
        "revenue": {"value": None, "available": False, "blocker": "B06"},
        "trial_cohorts": cohorts,
        "content_usage_30d": {
            "lessons_completed": completions,
            "tests_submitted": tests,
            "written_sealed": written,
            "engaged_learners": engaged,
        },
    }


# ------------------------------------------------------------------ route
router = APIRouter(prefix="/v1/admin", tags=["business overview"])
DB = Annotated[Session, Depends(get_session)]
Viewer = Annotated[Principal, Depends(require(Permission.view_business_overview))]


class Unavailable(BaseModel):
    value: int | None
    available: bool
    blocker: str


class TrialCohort(BaseModel):
    week_start: str
    started: int
    running: int
    ended: int
    converted_to_paid: int
    open: bool


class ContentUsage(BaseModel):
    lessons_completed: int
    tests_submitted: int
    written_sealed: int
    engaged_learners: int


class BusinessOverview(BaseModel):
    report_version: int
    generated_at: datetime
    definitions: dict[str, str]
    learners: int
    active_7d: int
    active_30d: int
    test_accounts: int
    entitlements_active: dict[str, int]
    verified_purchases: Unavailable
    refunds: Unavailable
    revenue: Unavailable
    trial_cohorts: list[TrialCohort]
    content_usage_30d: ContentUsage


@router.get(
    "/business-overview",
    response_model=BusinessOverview,
    summary="Business overview: aggregate figures with definitions (MFA)",
)
def business_overview(db: DB, who: Viewer, response: Response) -> BusinessOverview:
    response.headers["Cache-Control"] = "private, no-store"
    return BusinessOverview(**report(db))
