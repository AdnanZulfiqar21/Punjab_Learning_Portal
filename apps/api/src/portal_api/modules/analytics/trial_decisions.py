"""Trial decision quality and false blocks by cohort (roadmap P14.S8.T4; TRIAL-QUALITY-01).

For each Pakistan ISO week of trial claims (learners only: no staff, no test accounts), from our own records:

* **claims** and how many came from the apps (each needs one device check once DeviceCheck and Play Integrity
  exist, B07);
* **unknown verdicts:** claims whose device evidence could not be evaluated (provider unavailable or not configured);
* **denials:** claims refused because the device had already been used for a trial (`device_used`);
* **appeals:** denied learners who then asked for help about access, or whose case a reviewer decided;
* **overturned denials:** denied learners a reviewer later gave an exception, the false-block proxy. The launch
  target is under 2 % of denials, reviewed monthly; a week without denials has no rate rather than a perfect one.
* **review required:** claims still unresolved after the 7-day recovery window.

Trial-specific cost uses the unit rates finance entered for the cohort economics report (ECONOMICS-01): device
checks and support tickets are priced when their rate is set; sign-in codes (B04) and video minutes (B05) aren't
measured yet. Device verdicts in development come from the fixture adapter, so these figures prove nothing about
real device recall until B07/B08. The owner of appeals and false-block review is the student operations lead, an
owner appointment (P14.S8.T1) that is still open.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, exists, func, select
from sqlalchemy.orm import Session

from portal_api.days import week_of
from portal_api.db import get_session
from portal_api.modules.identity.deps import Principal, require
from portal_api.modules.identity.permissions import Permission

REPORT_VERSION = 1
WEEKS = 12
TARGET_PERCENT = Decimal("2")


def _pct(n: int, of: int) -> Decimal | None:
    return (Decimal(100 * n) / of).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) if of else None


def _money(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def report(db: Session) -> dict[str, Any]:
    from portal_api.config import get_settings
    from portal_api.modules.access.trial_devices import TrialClaim, TrialException
    from portal_api.modules.analytics.economics import current_rates
    from portal_api.modules.identity.models import AppUser, StaffRoleGrant
    from portal_api.modules.support.models import SupportTicket

    now: datetime = db.execute(select(func.now())).scalar_one()
    staff = exists().where(StaffRoleGrant.user_id == AppUser.id, StaffRoleGrant.revoked_at.is_(None))
    learner_ids = select(AppUser.id).where(
        AppUser.status != "deleted", ~staff, AppUser.issuer != get_settings().dev_auth_issuer
    )
    week = week_of(TrialClaim.created_at)
    denied = and_(TrialClaim.status == "CLOSED_INELIGIBLE", TrialClaim.outcome == "device_used")
    later_exception = exists().where(
        TrialException.user_id == TrialClaim.user_id, TrialException.created_at >= TrialClaim.created_at
    )
    later_ticket = exists().where(
        SupportTicket.user_id == TrialClaim.user_id,
        SupportTicket.category == "access",
        SupportTicket.created_at >= TrialClaim.created_at,
    )
    rows = db.execute(
        select(
            week.label("week"),
            func.count(),
            func.count().filter(TrialClaim.surface.in_(("ios", "android"))),
            func.count().filter(TrialClaim.evidence["verdict"].astext == "unknown"),
            func.count().filter(denied),
            func.count().filter(denied, later_ticket | later_exception),
            func.count().filter(denied, later_exception),
            func.count().filter(TrialClaim.status == "REVIEW_REQUIRED"),
            func.count(func.distinct(TrialClaim.user_id)).filter(denied, later_ticket),
        )
        .where(TrialClaim.user_id.in_(learner_ids), TrialClaim.created_at >= now - timedelta(weeks=WEEKS))
        .group_by(week)
        .order_by(week.desc())
    ).all()
    rates = current_rates(db)
    check_rate, ticket_rate = rates.get("attestation_per_1000"), rates.get("support_per_ticket")
    cohorts = []
    for w, claims, native, unknown, denials, appeals, overturned, review, appeal_tickets in rows:
        overturned_pct = _pct(overturned, denials)
        cost = []
        if check_rate is not None:
            checks = Decimal(native) * check_rate.amount / 1000
            cost.append({"line": "Device checks", "currency": check_rate.currency, "amount": _money(checks)})
        if ticket_rate is not None:
            tickets = Decimal(appeal_tickets) * ticket_rate.amount
            line = "Access help requests after a denial"
            cost.append({"line": line, "currency": ticket_rate.currency, "amount": _money(tickets)})
        cohorts.append(
            {
                "week_start": w.date().isoformat(),
                "claims": int(claims),
                "app_claims": int(native),
                "unknown_verdicts": int(unknown),
                "unknown_rate": _pct(unknown, claims),
                "denials": int(denials),
                "denial_rate": _pct(denials, claims),
                "appeals": int(appeals),
                "appeal_rate": _pct(appeals, denials),
                "overturned_denials": int(overturned),
                "overturned_rate": overturned_pct,
                "meets_target": None if overturned_pct is None else overturned_pct < TARGET_PERCENT,
                "review_required": int(review),
                "trial_cost": cost,
            }
        )
    return {
        "report_version": REPORT_VERSION,
        "generated_at": now,
        "weeks": WEEKS,
        "target_overturned_percent": TARGET_PERCENT,
        "cohorts": cohorts,
        "unmeasured_costs": ["Sign-in codes (OTP): sent by the identity provider (B04)", "Video minutes (B05)"],
        "appeals_owner": None,
        "appeals_owner_note": "The student operations lead owns appeals and false-block review; the owner hasn't "
        "named one yet (P14.S8.T1).",
        "evidence_note": "Device verdicts come from the development fixture adapter until DeviceCheck and Play "
        "Integrity exist (B07, B08); these figures say nothing about real device recall.",
        "definitions": {
            "cohort": "Trial claims by the Pakistan ISO week they were made; learners only, test accounts excluded.",
            "unknown_rate": "Claims whose device evidence couldn't be evaluated ÷ claims.",
            "denial_rate": "Claims refused because the device had already been used for a trial ÷ claims.",
            "appeal_rate": "Denied claims followed by an access help request or a reviewer's decision ÷ denials.",
            "overturned_rate": "Denied claims followed by a reviewer's exception ÷ denials (false-block proxy; target "
            "under 2 %, reviewed monthly). No denials means no rate, not a perfect one.",
            "review_required": "Claims still unresolved after the 7-day recovery window.",
            "trial_cost": "Measured quantities times the rates finance entered in the cohort economics report.",
        },
    }


# ------------------------------------------------------------------ route
router = APIRouter(prefix="/v1/admin/analytics", tags=["analytics"])
DB = Annotated[Session, Depends(get_session)]
Viewer = Annotated[Principal, Depends(require(Permission.view_business_overview))]


class CostAmount(BaseModel):
    line: str
    currency: str
    amount: Decimal


class TrialDecisionCohort(BaseModel):
    week_start: str
    claims: int
    app_claims: int
    unknown_verdicts: int
    unknown_rate: Decimal | None
    denials: int
    denial_rate: Decimal | None
    appeals: int
    appeal_rate: Decimal | None
    overturned_denials: int
    overturned_rate: Decimal | None = Field(description="False-block proxy; null when there were no denials")
    meets_target: bool | None
    review_required: int
    trial_cost: list[CostAmount]


class TrialDecisionReport(BaseModel):
    report_version: int
    generated_at: datetime
    weeks: int
    target_overturned_percent: Decimal
    cohorts: list[TrialDecisionCohort]
    unmeasured_costs: list[str]
    appeals_owner: str | None
    appeals_owner_note: str
    evidence_note: str
    definitions: dict[str, str]


@router.get(
    "/trial-decisions",
    response_model=TrialDecisionReport,
    summary="Trial decision quality and false blocks by cohort (owner, finance; MFA)",
)
def trial_decision_report(db: DB, who: Viewer, response: Response) -> TrialDecisionReport:
    response.headers["Cache-Control"] = "private, no-store"
    return TrialDecisionReport(**report(db))
