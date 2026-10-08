"""Access decisions (roadmap §16.2, P14.S5, §20.13.4).

Proposed defaults recorded in DECISIONS (owner may change): previews (catalogue, outlines, published lessons) are free;
starting practice tests or written assessment needs an active entitlement. One `PLATFORM_TRIAL_30D` per account,
starting at the grant's commit time and ending exactly 30 x 24 h later; retries return the original dates; prior paid
history means no introductory trial (T8). Native device recall (DeviceCheck/Play Integrity) is not available yet
(BLOCKERS B07/B08), so the decision uses account history only and says so.

Written allowance (§20.13.4): units are weighted per question (short 1, long 2). Starting reserves the form's maximum,
sealing accepts only questions with submitted work and releases the rest, the first released marks consume once, and
an unsealed expiry releases everything. At most two unsealed written permits per account. Every transition is an
idempotent ledger event; nothing is rewritten.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from portal_api.errors import AppError, Conflict
from portal_api.modules.access.models import (
    OFFER_TERMS_VERSION,
    TRIAL_PROGRAM,
    AllowanceEvent,
    Entitlement,
    TrialGrant,
)
from portal_api.modules.audit.models import record

TRIAL_PERIOD = timedelta(days=30)
TRIAL_WRITTEN_UNITS = 10  # proposed default pending measured cost (WA-D07)
QUESTION_WEIGHTS = {"short": 1, "long": 2}
MAX_OPEN_WRITTEN_PERMITS = 2


class AccessRequired(AppError):
    status = 403
    code = "ACCESS_REQUIRED"


class AllowanceExhausted(AppError):
    status = 403
    code = "ALLOWANCE_EXHAUSTED"


def db_now(db: Session) -> datetime:
    now: datetime = db.execute(select(func.clock_timestamp())).scalar_one()
    return now


# ------------------------------------------------------------------ entitlements and access
def active_entitlements(db: Session, user_id: uuid.UUID, now: datetime) -> list[Entitlement]:
    return list(
        db.scalars(
            select(Entitlement)
            .where(
                Entitlement.user_id == user_id,
                Entitlement.status == "active",
                Entitlement.starts_at <= now,
                Entitlement.ends_at > now,
            )
            .order_by(Entitlement.ends_at)
        )
    )


def require_access(db: Session, user_id: uuid.UUID, *, purpose: str) -> None:
    """New protected starts need a currently valid entitlement. Already-started attempts are never checked again."""
    if not active_entitlements(db, user_id, db_now(db)):
        trial = db.scalar(select(TrialGrant).where(TrialGrant.user_id == user_id, TrialGrant.program == TRIAL_PROGRAM))
        raise AccessRequired(
            f"{purpose} needs an active plan."
            + (" Your free trial has ended." if trial else " You can start your free 30-day trial."),
            trial_available=trial is None and not _has_paid_history(db, user_id),
        )


def _has_paid_history(db: Session, user_id: uuid.UUID) -> bool:
    count = db.scalar(
        select(func.count())
        .select_from(Entitlement)
        .where(Entitlement.user_id == user_id, Entitlement.source == "paid")
    )
    return bool(count)


# ------------------------------------------------------------------ trial
def trial_status(db: Session, user_id: uuid.UUID) -> dict[str, Any]:
    now = db_now(db)
    grant = db.scalar(select(TrialGrant).where(TrialGrant.user_id == user_id, TrialGrant.program == TRIAL_PROGRAM))
    if grant is None:
        paid = _has_paid_history(db, user_id)
        return {
            "program": TRIAL_PROGRAM,
            "eligible": not paid,
            "status": "available" if not paid else "not_eligible",
            "granted_at": None,
            "ends_at": None,
            "reason": None if not paid else "Trials are for new learners; you have had a paid plan.",
        }
    state = grant.status if grant.status != "active" else ("active" if grant.ends_at > now else "ended")
    return {
        "program": TRIAL_PROGRAM,
        "eligible": False,
        "status": state,
        "granted_at": grant.granted_at,
        "ends_at": grant.ends_at,
        "reason": None,
    }


def start_trial(db: Session, user_id: uuid.UUID, *, client: str) -> TrialGrant:
    existing = db.scalar(select(TrialGrant).where(TrialGrant.user_id == user_id, TrialGrant.program == TRIAL_PROGRAM))
    if existing is not None:
        return existing  # retries and second activations return the original dates; no second trial
    if _has_paid_history(db, user_id):
        raise Conflict("The free trial is for new learners. Your account has had a paid plan.")
    now = db_now(db)
    grant = TrialGrant(
        id=uuid.uuid4(),
        user_id=user_id,
        program=TRIAL_PROGRAM,
        offer_terms_version=OFFER_TERMS_VERSION,
        granted_at=now,
        ends_at=now + TRIAL_PERIOD,
        status="active",
        client=client,
    )
    try:
        db.add(grant)
        db.flush()  # the unique (user, program) constraint decides concurrent activations
    except IntegrityError:
        db.rollback()
        winner = db.scalar(select(TrialGrant).where(TrialGrant.user_id == user_id, TrialGrant.program == TRIAL_PROGRAM))
        assert winner is not None
        return winner
    ent = Entitlement(
        user_id=user_id,
        source="trial",
        starts_at=now,
        ends_at=grant.ends_at,
        written_units=TRIAL_WRITTEN_UNITS,
        reason=f"{TRIAL_PROGRAM} terms v{OFFER_TERMS_VERSION}",
    )
    db.add(ent)
    db.flush()
    grant.entitlement_id = ent.id
    record(
        db,
        actor=user_id,
        action="trial.granted",
        target_type="app_user",
        target_id=str(user_id),
        details={
            "program": TRIAL_PROGRAM,
            "ends_at": grant.ends_at.isoformat(),
            "client": client,
            "device_check": "unavailable (B07/B08); account history only",
        },
    )
    db.commit()
    db.refresh(grant)
    return grant


def grant_entitlement(
    db: Session, actor: uuid.UUID, user_id: uuid.UUID, *, source: str, days: int, written_units: int, reason: str
) -> Entitlement:
    now = db_now(db)
    ent = Entitlement(
        user_id=user_id,
        source=source,
        starts_at=now,
        ends_at=now + timedelta(days=days),
        written_units=written_units,
        reason=reason.strip(),
        granted_by=actor,
    )
    db.add(ent)
    db.flush()
    record(
        db,
        actor=actor,
        action="entitlement.granted",
        target_type="app_user",
        target_id=str(user_id),
        details={
            "entitlement": str(ent.id),
            "source": source,
            "days": days,
            "written_units": written_units,
            "reason": reason.strip(),
        },
    )
    db.commit()
    db.refresh(ent)
    return ent


def revoke_entitlement(db: Session, actor: uuid.UUID, entitlement_id: uuid.UUID, reason: str) -> Entitlement:
    ent = db.get(Entitlement, entitlement_id)
    if ent is None:
        from portal_api.errors import NotFound

        raise NotFound("Entitlement not found.")
    if ent.status != "active":
        raise Conflict("This entitlement is not active.")
    ent.status = "revoked"
    ent.revoked_at = db_now(db)
    ent.revoke_reason = reason.strip()
    record(
        db,
        actor=actor,
        action="entitlement.revoked",
        target_type="app_user",
        target_id=str(ent.user_id),
        details={"entitlement": str(ent.id), "reason": reason.strip()},
    )
    db.commit()
    db.refresh(ent)
    return ent


# ------------------------------------------------------------------ written allowance (§20.13.4)
def _events(db: Session, entitlement_ids: list[uuid.UUID]) -> list[AllowanceEvent]:
    if not entitlement_ids:
        return []
    return list(db.scalars(select(AllowanceEvent).where(AllowanceEvent.entitlement_id.in_(entitlement_ids))))


def _holds(events: list[AllowanceEvent]) -> tuple[int, int, int, int]:
    """(reserved_open, accepted_unconsumed, consumed, remedy) across the given events."""
    by_attempt: dict[uuid.UUID, dict[str, int]] = {}
    remedy = 0
    for e in events:
        if e.kind == "REMEDY_CREDIT":
            remedy += e.units
            continue
        by_attempt.setdefault(e.attempt_id, {})[e.kind] = e.units
    reserved = accepted = consumed = 0
    for kinds in by_attempt.values():
        if "CONSUMED" in kinds:
            consumed += kinds["CONSUMED"]
        elif "RELEASED" in kinds and "ACCEPTED" not in kinds:
            continue
        elif "ACCEPTED" in kinds:
            accepted += kinds["ACCEPTED"]
        elif "RESERVED" in kinds:
            reserved += kinds["RESERVED"]
    return reserved, accepted, consumed, remedy


def allowance(db: Session, user_id: uuid.UUID) -> dict[str, int]:
    ents = [e for e in active_entitlements(db, user_id, db_now(db)) if e.written_units > 0]
    granted = sum(e.written_units for e in ents)
    reserved, accepted, consumed, remedy = _holds(_events(db, [e.id for e in ents]))
    return {
        "granted": granted,
        "reserved": reserved,
        "accepted": accepted,
        "consumed": consumed,
        "available": max(0, granted + remedy - reserved - accepted - consumed),
    }


def weight_of(question_type: str | None) -> int:
    return QUESTION_WEIGHTS.get(question_type or "short", 1)


def permit_lock_key(user_id: uuid.UUID | str) -> int:
    """Transaction advisory-lock key that serializes written permit admission per account (review R03)."""
    v = uuid.UUID(str(user_id)).int >> 64
    return v - (1 << 64) if v >= (1 << 63) else v  # signed 64-bit for pg_advisory_xact_lock


def lock_permit_admission(db: Session, user_id: uuid.UUID) -> None:
    """Serialize every permit admission for this account until the transaction ends. Held only for the short
    admission transaction; a key collision between two accounts only adds waiting, never a wrong decision."""
    db.execute(select(func.pg_advisory_xact_lock(permit_lock_key(user_id))))


def reserve(db: Session, user_id: uuid.UUID, attempt_id: uuid.UUID, units: int, *, open_permits: int) -> None:
    """Inside the written start transaction, after `lock_permit_admission` and an open count taken under it.
    Also locks the funding entitlement so starts from different paths can't overspend it."""
    if open_permits >= MAX_OPEN_WRITTEN_PERMITS:
        raise AllowanceExhausted(
            f"Finish or submit your open written tests first (at most {MAX_OPEN_WRITTEN_PERMITS})."
        )
    now = db_now(db)
    ents = list(
        db.scalars(
            select(Entitlement)
            .where(
                Entitlement.user_id == user_id,
                Entitlement.status == "active",
                Entitlement.starts_at <= now,
                Entitlement.ends_at > now,
                Entitlement.written_units > 0,
            )
            .order_by(Entitlement.ends_at)
            .with_for_update()
        )
    )
    for ent in ents:  # use the bucket that expires first
        reserved, accepted, consumed, remedy = _holds(_events(db, [ent.id]))
        if ent.written_units + remedy - reserved - accepted - consumed >= units:
            db.add(
                AllowanceEvent(
                    user_id=user_id, entitlement_id=ent.id, attempt_id=attempt_id, kind="RESERVED", units=units
                )
            )
            db.flush()
            return
    raise AllowanceExhausted(
        "Your plan's written-marking allowance can't cover this test.",
        needed=units,
        available=allowance(db, user_id)["available"],
    )


def accept(db: Session, attempt_id: uuid.UUID, units: int, detail: dict[str, Any]) -> None:
    """Inside the seal transaction: bind the submitted questions; the rest of the reservation is released."""
    res = db.scalar(
        select(AllowanceEvent).where(AllowanceEvent.attempt_id == attempt_id, AllowanceEvent.kind == "RESERVED")
    )
    if res is None or db.scalar(
        select(AllowanceEvent).where(AllowanceEvent.attempt_id == attempt_id, AllowanceEvent.kind == "ACCEPTED")
    ):
        return
    db.add(
        AllowanceEvent(
            user_id=res.user_id,
            entitlement_id=res.entitlement_id,
            attempt_id=attempt_id,
            kind="ACCEPTED",
            units=min(units, res.units),
            detail=detail,
        )
    )


def consume(db: Session, attempt_id: uuid.UUID) -> None:
    """Inside the first result release: consume the accepted units exactly once."""
    acc = db.scalar(
        select(AllowanceEvent).where(AllowanceEvent.attempt_id == attempt_id, AllowanceEvent.kind == "ACCEPTED")
    )
    if acc is None or db.scalar(
        select(AllowanceEvent).where(AllowanceEvent.attempt_id == attempt_id, AllowanceEvent.kind == "CONSUMED")
    ):
        return
    db.add(
        AllowanceEvent(
            user_id=acc.user_id,
            entitlement_id=acc.entitlement_id,
            attempt_id=attempt_id,
            kind="CONSUMED",
            units=acc.units,
        )
    )


def release(db: Session, attempt_id: uuid.UUID, reason: str) -> None:
    """Unsealed expiry/cancellation: return the whole reservation (no trial restart, no extension)."""
    res = db.scalar(
        select(AllowanceEvent).where(AllowanceEvent.attempt_id == attempt_id, AllowanceEvent.kind == "RESERVED")
    )
    if res is None:
        return
    done = db.scalar(
        select(AllowanceEvent).where(
            AllowanceEvent.attempt_id == attempt_id, AllowanceEvent.kind.in_(["ACCEPTED", "RELEASED"])
        )
    )
    if done is not None:
        return
    db.add(
        AllowanceEvent(
            user_id=res.user_id,
            entitlement_id=res.entitlement_id,
            attempt_id=attempt_id,
            kind="RELEASED",
            units=res.units,
            detail={"reason": reason},
        )
    )
