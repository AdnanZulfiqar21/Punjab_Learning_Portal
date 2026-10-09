"""Support staff tools (P15.S3.T3): scoped learner lookup, a redacted activity timeline including trial decisions,
and explicit, time-limited, audited assisted access.

* Lookup is by exact email only (no browsing or partial matches) and finds learner accounts, never staff.
* The timeline lists what happened and when (account, trial grants, claims and device decisions, exceptions, access
  sources, attempts, help requests, account actions). It never shows answers, uploads, message bodies, installation
  identifiers or provider evidence.
* Assisted access is granted by a support staff member for one open request of that learner, with a reason, for at
  most 30 minutes. While it is active the timeline also shows result summaries. The learner is told and can end it.
Every lookup, view, grant and revocation is audited.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from portal_api.errors import Conflict, NotFound
from portal_api.modules.access.models import Entitlement, TrialGrant
from portal_api.modules.access.trial_devices import TrialClaim, TrialClaimEvent, TrialDeviceUse, TrialException
from portal_api.modules.assessment.models import Attempt, ScoreVersion
from portal_api.modules.audit.models import AuditEvent, record
from portal_api.modules.identity.deps import Principal
from portal_api.modules.identity.models import AppUser, StaffRoleGrant
from portal_api.modules.notifications import service as notifications
from portal_api.modules.support.models import SupportAssistedAccess, SupportTicket
from portal_api.modules.written.models import WrittenAttempt, WrittenFile

MAX_ASSIST_MINUTES = 30
TIMELINE_LIMIT = 300


def _now(db: Session) -> datetime:
    now: datetime = db.execute(select(func.clock_timestamp())).scalar_one()
    return now


def _learner(db: Session, user_id: uuid.UUID) -> AppUser:
    """A learner account; staff accounts are outside support's scope."""
    user = db.get(AppUser, user_id)
    if user is None or user.status == "deleted":
        raise NotFound("Learner not found.")
    is_staff = db.scalar(
        select(func.count(StaffRoleGrant.id)).where(
            StaffRoleGrant.user_id == user_id, StaffRoleGrant.revoked_at.is_(None)
        )
    )
    if is_staff:
        raise NotFound("Learner not found.")
    return user


def find_learner(db: Session, who: Principal, email: str) -> AppUser:
    norm = email.strip().lower()
    user = db.scalar(select(AppUser).where(func.lower(AppUser.email) == norm, AppUser.status != "deleted").limit(1))
    try:
        found = _learner(db, user.id) if user else None
    except NotFound:
        found = None
    record(
        db,
        actor=who.user.id,
        action="support.lookup",
        target_type="app_user",
        target_id=str(found.id) if found else "-",
        details={"found": found is not None},  # the searched address itself is not kept
    )
    db.commit()
    if found is None:
        raise NotFound("No learner account has that email.")
    return found


def open_requests(db: Session, user_id: uuid.UUID) -> int:
    n = db.scalar(
        select(func.count(SupportTicket.id)).where(SupportTicket.user_id == user_id, SupportTicket.status != "resolved")
    )
    return int(n or 0)


def active_assist(db: Session, staff_id: uuid.UUID, user_id: uuid.UUID) -> SupportAssistedAccess | None:
    return db.scalar(
        select(SupportAssistedAccess)
        .where(
            SupportAssistedAccess.staff_id == staff_id,
            SupportAssistedAccess.user_id == user_id,
            SupportAssistedAccess.revoked_at.is_(None),
            SupportAssistedAccess.expires_at > func.clock_timestamp(),
        )
        .order_by(SupportAssistedAccess.granted_at.desc())
        .limit(1)
    )


def timeline(
    db: Session, who: Principal, user_id: uuid.UUID
) -> tuple[AppUser, SupportAssistedAccess | None, list[dict[str, Any]]]:
    user = _learner(db, user_id)
    assist = active_assist(db, who.user.id, user_id)
    ev: list[dict[str, Any]] = [{"at": user.created_at, "kind": "account.created", "detail": {}}]

    def add(at: datetime | None, kind: str, **detail: Any) -> None:
        if at is not None:
            ev.append({"at": at, "kind": kind, "detail": detail})

    for g in db.scalars(select(TrialGrant).where(TrialGrant.user_id == user_id)):
        add(g.granted_at, "trial.granted", ends_at=g.ends_at.isoformat(), status=g.status, client=g.client)
    claims = {c.id: c for c in db.scalars(select(TrialClaim).where(TrialClaim.user_id == user_id))}
    if claims:
        for e in db.scalars(select(TrialClaimEvent).where(TrialClaimEvent.claim_id.in_(list(claims)))):
            add(
                e.at,
                "trial.claim",
                surface=claims[e.claim_id].surface,
                from_status=e.from_status,
                to_status=e.to_status,
                reason=e.reason,
            )
    for d in db.scalars(select(TrialDeviceUse).where(TrialDeviceUse.user_id == user_id)):
        add(d.authorized_at, "trial.device_authorized", surface=d.surface, method=d.method)
        add(d.removed_at, "trial.device_removed", surface=d.surface)
    for x in db.scalars(select(TrialException).where(TrialException.user_id == user_id)):
        add(x.created_at, "trial.exception", surface=x.surface, reason=x.reason, expires_at=x.expires_at.isoformat())
    for n in db.scalars(select(Entitlement).where(Entitlement.user_id == user_id)):
        add(
            n.created_at,
            "access.granted",
            source=n.source,
            starts_at=n.starts_at.isoformat(),
            ends_at=n.ends_at.isoformat(),
        )
        add(n.revoked_at, f"access.{n.status}", source=n.source)
    for a in db.scalars(select(Attempt).where(Attempt.user_id == user_id)):
        add(a.started_at, "practice.started", attempt_id=str(a.id))
        if a.finalised_at is not None:
            done: dict[str, Any] = {"attempt_id": str(a.id), "how": a.finalise_reason}
            if assist is not None:
                s = db.scalar(
                    select(ScoreVersion)
                    .where(ScoreVersion.attempt_id == a.id)
                    .order_by(ScoreVersion.version.desc())
                    .limit(1)
                )
                if s is not None:
                    done["score"] = {"raw": s.raw, "maximum": s.maximum, "status": s.status}
            add(a.finalised_at, "practice.finished", **done)
    for w in db.scalars(select(WrittenAttempt).where(WrittenAttempt.user_id == user_id)):
        add(w.started_at, "written.started", attempt_id=str(w.id))
        sealed: dict[str, Any] = {"attempt_id": str(w.id)}
        if assist is not None:
            files = db.scalar(
                select(func.count(WrittenFile.id)).where(
                    WrittenFile.attempt_id == w.id, WrittenFile.status != "withdrawn"
                )
            )
            sealed["files"] = int(files or 0)
        add(w.sealed_at, "written.submitted", **sealed)
        add(w.expired_at, "written.expired", attempt_id=str(w.id))
    for t in db.scalars(select(SupportTicket).where(SupportTicket.user_id == user_id)):
        add(t.created_at, "support.opened", ticket_id=str(t.id), category=t.category, status=t.status)
    for r in db.scalars(
        select(AuditEvent).where(AuditEvent.target_type == "app_user", AuditEvent.target_id == str(user_id))
    ):
        if r.action.startswith("support."):
            continue  # staff's own lookups and views are audit history, not learner activity
        add(r.at, f"account.{r.action}", by_staff=r.actor_user_id is not None and r.actor_user_id != user_id)

    ev.sort(key=lambda e: e["at"], reverse=True)
    record(
        db,
        actor=who.user.id,
        action="support.timeline_viewed",
        target_type="app_user",
        target_id=str(user_id),
        details={"assisted_access": str(assist.id) if assist else None},
    )
    db.commit()
    return user, assist, ev[:TIMELINE_LIMIT]


def grant_assist(
    db: Session, who: Principal, user_id: uuid.UUID, ticket_id: uuid.UUID, reason: str, minutes: int
) -> SupportAssistedAccess:
    _learner(db, user_id)
    t = db.get(SupportTicket, ticket_id)
    if t is None or t.user_id != user_id:
        raise NotFound("Request not found for this learner.")
    if t.status == "resolved":
        raise Conflict("Assisted access needs one of the learner's open requests.")
    if active_assist(db, who.user.id, user_id) is not None:
        raise Conflict("You already have assisted access for this learner.")
    minutes = min(minutes, MAX_ASSIST_MINUTES)
    now = _now(db)
    row = SupportAssistedAccess(
        id=uuid.uuid4(),
        user_id=user_id,
        staff_id=who.user.id,
        ticket_id=t.id,
        reason=reason.strip(),
        granted_at=now,
        expires_at=now + timedelta(minutes=minutes),
    )
    db.add(row)
    record(
        db,
        actor=who.user.id,
        action="support.assisted_access_granted",
        target_type="app_user",
        target_id=str(user_id),
        details={"access": str(row.id), "ticket": str(t.id), "minutes": minutes, "reason": row.reason},
    )
    notifications.notify(
        db,
        user_id,
        "support.assisted_access",
        {"subject": t.subject, "minutes": str(minutes)},
        dedupe_key=f"assist-{row.id}",
    )
    db.commit()
    db.refresh(row)
    return row


def revoke_assist(db: Session, who: Principal, access_id: uuid.UUID, *, as_learner: bool) -> None:
    row = db.get(SupportAssistedAccess, access_id)
    if row is None or (row.user_id if as_learner else row.staff_id) != who.user.id:
        raise NotFound("Assisted access not found.")
    now = _now(db)
    if row.revoked_at is not None or row.expires_at <= now:
        raise Conflict("This assisted access has already ended.")
    row.revoked_at = now
    row.revoked_by = who.user.id
    record(
        db,
        actor=who.user.id,
        action="support.assisted_access_ended",
        target_type="app_user",
        target_id=str(row.user_id),
        details={"access": str(row.id), "by": "learner" if as_learner else "staff"},
    )
    db.commit()


def my_assists(db: Session, user_id: uuid.UUID) -> list[SupportAssistedAccess]:
    return list(
        db.scalars(
            select(SupportAssistedAccess)
            .where(SupportAssistedAccess.user_id == user_id)
            .order_by(SupportAssistedAccess.granted_at.desc())
            .limit(50)
        )
    )
