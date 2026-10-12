"""Trial and paid cohort economics (roadmap P16.S2.T4, decision D13; ECONOMICS-01).

For each population, every cost line is a **measured quantity** from our own records times a **unit rate entered by
finance** with its source. Nothing is estimated or defaulted:

* A quantity we can't measure yet (video delivery and storage before a media provider, sign-in codes sent by the
  identity provider, OCR/model use, payment fees and refunds) is shown as unavailable with its blocker.
* A rate nobody has entered is shown as not set, and that line's cost is unknown.
* Totals are the known part only. The report lists what is missing and never presents a partial total as complete.
* Contribution per paying learner needs verified payments and prices (B06, D02), so it is unavailable.

Labour is counted once: written marking appears only as reviewed scripts (a fully loaded cost per script from the
staffing figures, W09), and support only as tickets, so the same hours are never charged twice.

Populations are learners only (no staff role, no test accounts), as in the business overview, over the last
`WINDOW_DAYS` days. Each learner is in at most one population, in this order:

* **paying:** paid access now;
* **trial:** a trial running now;
* **completed_trial:** a trial that ended in the window without paid access.

The owner reviews this report, then sets the cohort budget, fair-use terms and rollout limits before funded
acquisition (D13). The report supports that decision; it does not make it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, and_, exists, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base, get_session
from portal_api.errors import Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.identity.deps import Principal, require
from portal_api.modules.identity.permissions import Permission

REPORT_VERSION = 1
WINDOW_DAYS = 30
GB = Decimal(1024**3)


@dataclass(frozen=True)
class Rate:
    key: str
    label: str
    unit: str  # what one rate amount buys
    per: int  # quantity the amount is quoted for (1,000 emails, 1 learner-month, ...)


RATES: tuple[Rate, ...] = (
    Rate("hosting_per_learner_month", "Hosting share", "per learner-month", 1),
    Rate("production_per_learner_month", "Academic production amortisation", "per learner-month", 1),
    Rate("video_delivery_per_1000_minutes", "Video delivery", "per 1,000 delivered minutes", 1000),
    Rate("otp_per_1000", "Sign-in codes (OTP)", "per 1,000 codes", 1000),
    Rate("email_per_1000", "Email", "per 1,000 emails", 1000),
    Rate("attestation_per_1000", "Device attestation checks", "per 1,000 checks", 1000),
    Rate("support_per_ticket", "Support (fully loaded)", "per ticket", 1),
    Rate("review_per_script", "Written marking (fully loaded, W09)", "per reviewed script", 1),
    Rate("evidence_storage_per_gb_month", "Private evidence storage", "per GB-month", 1),
    Rate("ocr_per_1000_pages", "OCR and model use", "per 1,000 pages", 1000),
)
RATE_BY_KEY = {r.key: r for r in RATES}


class CostRate(Base):
    """One unit-rate version entered by finance. Append-only: the newest row per key is current."""

    __tablename__ = "cost_rate"
    __table_args__ = (
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="cost_rate_currency"),
        CheckConstraint("amount >= 0", name="cost_rate_amount"),
        Index("ix_cost_rate_current", "key", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(40))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    currency: Mapped[str] = mapped_column(String(3))
    source_note: Mapped[str] = mapped_column(Text)
    set_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def set_rate(db: Session, who: Principal, key: str, amount: Decimal, currency: str, source_note: str) -> CostRate:
    if key not in RATE_BY_KEY:
        raise Unprocessable("Choose one of the listed cost lines.")
    currency = currency.strip().upper()
    rates = current_rates(db)
    others = {r.currency for k, r in rates.items() if k != key}
    if others and currency not in others:
        raise Unprocessable(f"Enter this rate in {', '.join(sorted(others))}, the currency the other rates use.")
    row = CostRate(
        id=uuid.uuid4(), key=key, amount=amount, currency=currency, source_note=source_note.strip(), set_by=who.user.id
    )
    db.add(row)
    record(
        db,
        actor=who.user.id,
        action="economics.rate_set",
        target_type="cost_rate",
        target_id=key,
        details={"amount": str(amount), "currency": currency, "source_note": row.source_note},
    )
    db.commit()
    db.refresh(row)
    return row


def current_rates(db: Session) -> dict[str, CostRate]:
    latest = select(CostRate.key, func.max(CostRate.created_at).label("at")).group_by(CostRate.key).subquery()
    rows = db.scalars(
        select(CostRate).join(latest, and_(latest.c.key == CostRate.key, latest.c.at == CostRate.created_at))
    )
    return {r.key: r for r in rows}


# ------------------------------------------------------------------ measured quantities
@dataclass(frozen=True)
class Quantity:
    value: Decimal | None
    note: str
    blocker: str | None = None


UNMEASURED = {
    "video_delivery_per_1000_minutes": Quantity(None, "Delivered video minutes aren't measured yet.", "B05"),
    "otp_per_1000": Quantity(None, "Sign-in codes are sent by the identity provider.", "B04"),
    "ocr_per_1000_pages": Quantity(None, "No reading provider is approved.", "B10"),
}


def _populations(db: Session, now: datetime) -> dict[str, Any]:
    """Learner id subqueries for each population (mutually exclusive, in report order)."""
    from portal_api.config import get_settings
    from portal_api.modules.access.models import Entitlement, TrialGrant
    from portal_api.modules.identity.models import AppUser, StaffRoleGrant

    staff = exists().where(StaffRoleGrant.user_id == AppUser.id, StaffRoleGrant.revoked_at.is_(None))
    learner = and_(AppUser.status == "active", ~staff, AppUser.issuer != get_settings().dev_auth_issuer)
    paid_now = exists().where(
        Entitlement.user_id == AppUser.id,
        Entitlement.source == "paid",
        Entitlement.status == "active",
        Entitlement.starts_at <= now,
        Entitlement.ends_at > now,
    )
    trial_now = exists().where(
        TrialGrant.user_id == AppUser.id, TrialGrant.status == "active", TrialGrant.ends_at > now
    )
    trial_ended = exists().where(
        TrialGrant.user_id == AppUser.id,
        TrialGrant.ends_at <= now,
        TrialGrant.ends_at > now - timedelta(days=WINDOW_DAYS),
    )
    return {
        "paying": select(AppUser.id).where(learner, paid_now),
        "trial": select(AppUser.id).where(learner, ~paid_now, trial_now),
        "completed_trial": select(AppUser.id).where(learner, ~paid_now, ~trial_now, trial_ended),
    }


def _quantities(db: Session, ids: Any, now: datetime) -> tuple[int, dict[str, Quantity]]:
    from portal_api.modules.access.trial_devices import TrialClaim
    from portal_api.modules.notifications.models import NotificationDelivery
    from portal_api.modules.support.models import SupportTicket
    from portal_api.modules.written.models import WrittenAttempt, WrittenFile
    from portal_api.modules.written.review import WrittenReviewCase, WrittenScoreVersion

    since = now - timedelta(days=WINDOW_DAYS)
    learners = int(db.scalar(select(func.count()).select_from(ids.subquery())) or 0)

    def count(stmt: Any) -> Decimal:
        return Decimal(int(db.scalar(stmt) or 0))

    emails = count(
        select(func.count()).where(
            NotificationDelivery.user_id.in_(ids),
            NotificationDelivery.channel == "email",
            NotificationDelivery.status == "sent",
            NotificationDelivery.sent_at >= since,
        )
    )
    native_checks = count(
        select(func.count()).where(
            TrialClaim.user_id.in_(ids), TrialClaim.surface.in_(("ios", "android")), TrialClaim.created_at >= since
        )
    )
    tickets = count(select(func.count()).where(SupportTicket.user_id.in_(ids), SupportTicket.created_at >= since))
    scripts = count(
        select(func.count())
        .select_from(WrittenReviewCase)
        .join(WrittenAttempt, WrittenAttempt.id == WrittenReviewCase.attempt_id)
        .where(
            WrittenAttempt.user_id.in_(ids),
            WrittenReviewCase.status == "released",
            WrittenReviewCase.released_at >= since,
            # a teacher's decision; automatic closures and carried-forward versions involve no marking work
            exists().where(
                WrittenScoreVersion.case_id == WrittenReviewCase.id, WrittenScoreVersion.decision_method == "TEACHER"
            ),
        )
    )
    stored = Decimal(
        int(
            db.scalar(
                select(func.coalesce(func.sum(WrittenFile.size), 0))
                .join(WrittenAttempt, WrittenAttempt.id == WrittenFile.attempt_id)
                .where(WrittenAttempt.user_id.in_(ids))
            )
            or 0
        )
    )
    months = Decimal(learners) * Decimal(WINDOW_DAYS) / Decimal(30)
    return learners, {
        "hosting_per_learner_month": Quantity(months, f"Learners in this group, each for {WINDOW_DAYS} days."),
        "production_per_learner_month": Quantity(months, f"Learners in this group, each for {WINDOW_DAYS} days."),
        "email_per_1000": Quantity(emails, "Emails sent to these learners."),
        "attestation_per_1000": Quantity(
            native_checks,
            "Trial activations from the apps; each needs one provider check once DeviceCheck and Play Integrity "
            "exist (B07).",
        ),
        "support_per_ticket": Quantity(tickets, "Help requests these learners opened."),
        "review_per_script": Quantity(scripts, "Written reviews a teacher released (marking, rechecks, completions)."),
        "evidence_storage_per_gb_month": Quantity(
            (stored / GB).quantize(Decimal("0.0001")), "Answer-script files kept for these learners, in GB."
        ),
        **UNMEASURED,
    }


def _money(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def report(db: Session) -> dict[str, Any]:
    now: datetime = db.execute(select(func.now())).scalar_one()
    rates = current_rates(db)
    populations = []
    for key, ids in _populations(db, now).items():
        learners, quantities = _quantities(db, ids, now)
        lines: list[dict[str, Any]] = []
        totals: dict[str, Decimal] = {}
        missing: list[str] = []
        for rate in RATES:
            q, r = quantities[rate.key], rates.get(rate.key)
            cost = None
            if q.value is not None and r is not None:
                cost = _money(q.value * r.amount / rate.per)
                totals[r.currency] = totals.get(r.currency, Decimal(0)) + cost
            elif q.value is None:
                missing.append(f"{rate.label}: not measured ({q.blocker})")
            else:
                missing.append(f"{rate.label}: rate not set")
            lines.append(
                {
                    "key": rate.key,
                    "label": rate.label,
                    "quantity": q.value,
                    "quantity_note": q.note,
                    "blocker": q.blocker,
                    "rate_set": r is not None,
                    "cost": cost,
                    "currency": r.currency if r is not None else None,
                }
            )
        missing.append("Payment fees and refunds: no payment provider (B06)")
        populations.append(
            {
                "key": key,
                "learners": learners,
                "lines": lines,
                "known_cost": [{"currency": c, "amount": _money(v)} for c, v in sorted(totals.items())],
                "known_cost_per_learner": [
                    {"currency": c, "amount": _money(v / learners)} for c, v in sorted(totals.items()) if learners
                ],
                "complete": False,  # payment fees and refunds are always missing until B06
                "missing": missing,
            }
        )
    return {
        "report_version": REPORT_VERSION,
        "generated_at": now,
        "window_days": WINDOW_DAYS,
        "rates": [
            {
                "key": r.key,
                "label": r.label,
                "unit": r.unit,
                "amount": rates[r.key].amount if r.key in rates else None,
                "currency": rates[r.key].currency if r.key in rates else None,
                "source_note": rates[r.key].source_note if r.key in rates else None,
                "set_at": rates[r.key].created_at if r.key in rates else None,
            }
            for r in RATES
        ],
        "populations": populations,
        "contribution_per_paying_learner": {"value": None, "available": False, "blocker": "B06"},
        "definitions": {
            "paying": "Learners with paid access now.",
            "trial": "Learners on a running trial without paid access.",
            "completed_trial": f"Learners whose trial ended in the last {WINDOW_DAYS} days without paid access.",
            "cost": "Measured quantity times the current rate entered by finance. Lines without a measurement or a "
            "rate are left out of the known cost and listed as missing.",
            "labour": "Written marking is counted only per reviewed script and support only per ticket, each at a "
            "fully loaded rate, so the same hours are never counted twice.",
            "decision": "The owner reviews this report, then sets the cohort budget, fair-use terms and rollout "
            "limits before funded acquisition (D13).",
        },
    }


# ------------------------------------------------------------------ routes
RateKey = Literal[
    "hosting_per_learner_month",
    "production_per_learner_month",
    "video_delivery_per_1000_minutes",
    "otp_per_1000",
    "email_per_1000",
    "attestation_per_1000",
    "support_per_ticket",
    "review_per_script",
    "evidence_storage_per_gb_month",
    "ocr_per_1000_pages",
]
router = APIRouter(prefix="/v1/admin/analytics", tags=["analytics"])
DB = Annotated[Session, Depends(get_session)]
Viewer = Annotated[Principal, Depends(require(Permission.view_business_overview))]
Finance = Annotated[Principal, Depends(require(Permission.finance_operations))]


class RateIn(BaseModel):
    key: RateKey
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=4, description="Cost for the rate's quoted quantity")
    currency: str = Field(pattern=r"^[A-Za-z]{3}$")
    source_note: str = Field(
        min_length=10, max_length=2000, description="Where the figure comes from and when it was checked"
    )


class RateOut(BaseModel):
    key: str
    label: str
    unit: str
    amount: Decimal | None
    currency: str | None
    source_note: str | None
    set_at: datetime | None


class Money(BaseModel):
    currency: str
    amount: Decimal


class CostLine(BaseModel):
    key: str
    label: str
    quantity: Decimal | None = Field(description="Measured from our own records; null when it can't be measured yet")
    quantity_note: str
    blocker: str | None
    rate_set: bool
    cost: Decimal | None = Field(description="Quantity times the current rate; null when either is missing")
    currency: str | None


class Population(BaseModel):
    key: Literal["paying", "trial", "completed_trial"]
    learners: int
    lines: list[CostLine]
    known_cost: list[Money] = Field(description="The known part only, by currency")
    known_cost_per_learner: list[Money]
    complete: bool
    missing: list[str]


class UnavailableFigure(BaseModel):
    value: Decimal | None
    available: bool
    blocker: str


class EconomicsReport(BaseModel):
    report_version: int
    generated_at: datetime
    window_days: int
    rates: list[RateOut]
    populations: list[Population]
    contribution_per_paying_learner: UnavailableFigure
    definitions: dict[str, str]


@router.get(
    "/economics", response_model=EconomicsReport, summary="Trial and paid cohort economics (owner, finance; MFA)"
)
def economics_report(db: DB, who: Viewer, response: Response) -> EconomicsReport:
    response.headers["Cache-Control"] = "private, no-store"
    return EconomicsReport(**report(db))


@router.post(
    "/economics/rates",
    response_model=RateOut,
    status_code=201,
    summary="Enter a unit rate with its source (finance; MFA). Earlier rates are kept",
)
def set_economics_rate(db: DB, who: Finance, body: RateIn) -> RateOut:
    row = set_rate(db, who, body.key, body.amount, body.currency, body.source_note)
    rate = RATE_BY_KEY[row.key]
    return RateOut(
        key=row.key,
        label=rate.label,
        unit=rate.unit,
        amount=row.amount,
        currency=row.currency,
        source_note=row.source_note,
        set_at=row.created_at,
    )
