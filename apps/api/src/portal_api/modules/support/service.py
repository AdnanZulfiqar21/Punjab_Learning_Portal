"""Support tickets and academic error reports (P15.S3).

* Learners open tickets about their own account, access or attempts; references are validated against ownership.
* Academic reports name a question in the learner's own attempt; the server resolves the exact item and version and
  routes the report to reviewers scoped to that grade and subject. Learners never see internal IDs, keys or notes.
* Support staff (`view_support_context`) see all tickets with a minimal, redacted context; reviewers see academic
  reports in their scope without the learner's identity. Staff actions are audited.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from portal_api.errors import Conflict, NotFound, Unprocessable
from portal_api.modules.access import service as access
from portal_api.modules.assessment.models import Attempt, FormItem
from portal_api.modules.audit.models import record
from portal_api.modules.content.models import ContentItem, ContentVersion
from portal_api.modules.content.workflow import roles_in_scope
from portal_api.modules.identity.deps import Principal
from portal_api.modules.identity.models import AppUser
from portal_api.modules.identity.permissions import Permission, permissions_for
from portal_api.modules.support.models import SupportMessage, SupportTicket
from portal_api.modules.written.models import WrittenAttempt, WrittenFormItem

MAX_OPEN_TICKETS = 5


def _now(db: Session) -> datetime:
    now: datetime = db.execute(select(func.clock_timestamp())).scalar_one()
    return now


def _resolve_reference(db: Session, who: Principal, ref: dict[str, Any]) -> dict[str, Any]:
    """Validate that a reference belongs to the learner; for a question, resolve the exact item and version."""
    kind, rid, position = ref.get("kind"), ref.get("id"), ref.get("position")
    try:
        attempt_id = uuid.UUID(str(rid))
    except ValueError as e:
        raise Unprocessable("That reference isn't valid.") from e
    if kind == "attempt":
        attempt = db.get(Attempt, attempt_id)
        if attempt is None or attempt.user_id != who.user.id:
            raise NotFound("Attempt not found.")
        if position is None:
            return {"reference": {"kind": kind, "id": str(attempt_id)}}
        fi = db.scalar(select(FormItem).where(FormItem.form_id == attempt.form_id, FormItem.position == int(position)))
        if fi is None:
            raise NotFound("Question not found in that test.")
        item_id, version_id = fi.item_id, fi.version_id
    elif kind == "written_attempt":
        wa = db.get(WrittenAttempt, attempt_id)
        if wa is None or wa.user_id != who.user.id:
            raise NotFound("Attempt not found.")
        if position is None:
            return {"reference": {"kind": kind, "id": str(attempt_id)}}
        wfi = db.scalar(
            select(WrittenFormItem).where(
                WrittenFormItem.form_id == wa.form_id, WrittenFormItem.position == int(position)
            )
        )
        if wfi is None:
            raise NotFound("Question not found in that test.")
        item_id, version_id = wfi.item_id, wfi.question_version_id
    else:
        raise Unprocessable("Unknown reference kind.")
    item = db.get(ContentItem, item_id)
    assert item is not None
    return {
        "reference": {"kind": kind, "id": str(attempt_id), "position": int(position)},
        "content_item_id": item.id,
        "content_version_id": version_id,
        "grade_number": item.grade_number,
        "subject_code": item.subject_code,
    }


def create_ticket(
    db: Session, who: Principal, *, category: str, subject: str, body: str, reference: dict[str, Any] | None
) -> SupportTicket:
    open_count = db.scalar(
        select(func.count())
        .select_from(SupportTicket)
        .where(SupportTicket.user_id == who.user.id, SupportTicket.status != "resolved")
    )
    if (open_count or 0) >= MAX_OPEN_TICKETS:
        raise Conflict(f"You already have {MAX_OPEN_TICKETS} open requests. We'll reply to those first.")
    fields: dict[str, Any] = {"reference": {}}
    if reference:
        fields = _resolve_reference(db, who, reference)
    if category == "academic_report" and "content_item_id" not in fields:
        raise Unprocessable("Choose the question you're reporting from your test results.")
    now = _now(db)
    ticket = SupportTicket(
        user_id=who.user.id,
        category=category,
        subject=subject.strip(),
        status="open",
        created_at=now,
        updated_at=now,
        **fields,
    )
    db.add(ticket)
    db.flush()
    db.add(
        SupportMessage(ticket_id=ticket.id, author_id=who.user.id, from_staff=False, body=body.strip(), created_at=now)
    )
    db.commit()
    db.refresh(ticket)
    return ticket


def my_tickets(db: Session, who: Principal) -> list[SupportTicket]:
    return list(
        db.scalars(
            select(SupportTicket).where(SupportTicket.user_id == who.user.id).order_by(SupportTicket.updated_at.desc())
        )
    )


def own_ticket(db: Session, who: Principal, ticket_id: uuid.UUID) -> SupportTicket:
    t = db.get(SupportTicket, ticket_id)
    if t is None or t.user_id != who.user.id:
        raise NotFound("Request not found.")
    return t


def messages(db: Session, ticket: SupportTicket, *, include_internal: bool) -> list[SupportMessage]:
    stmt = select(SupportMessage).where(SupportMessage.ticket_id == ticket.id).order_by(SupportMessage.created_at)
    if not include_internal:
        stmt = stmt.where(SupportMessage.internal.is_(False))
    return list(db.scalars(stmt))


def learner_reply(db: Session, who: Principal, ticket_id: uuid.UUID, body: str) -> SupportTicket:
    t = own_ticket(db, who, ticket_id)
    now = _now(db)
    db.add(SupportMessage(ticket_id=t.id, author_id=who.user.id, from_staff=False, body=body.strip(), created_at=now))
    if t.status in ("waiting_learner", "resolved"):
        t.status = "open"
    t.updated_at = now
    db.commit()
    db.refresh(t)
    return t


# ------------------------------------------------------------------ staff
def _is_support(who: Principal) -> bool:
    return Permission.view_support_context in who.permissions


def _reviewer_scope_clause(db: Session, who: Principal) -> Any:
    """Academic reports visible to a reviewer: their grade/subject grants (SQL, before any limit)."""
    from sqlalchemy import and_, false, true

    from portal_api.modules.identity.models import StaffRoleGrant
    from portal_api.modules.identity.permissions import ROLE_PERMISSIONS

    reviewing = [r.value for r, perms in ROLE_PERMISSIONS.items() if Permission.review_content in perms]
    clauses: list[Any] = []
    for grant in db.scalars(
        select(StaffRoleGrant).where(
            StaffRoleGrant.user_id == who.user.id,
            StaffRoleGrant.revoked_at.is_(None),
            StaffRoleGrant.role.in_(reviewing),
        )
    ):
        scope = grant.scope or {}
        grades, subjects = scope.get("grades"), scope.get("subjects")
        if grades is None and subjects is None:
            return and_(SupportTicket.category == "academic_report", true())
        parts = [SupportTicket.category == "academic_report"]
        if grades is not None:
            parts.append(SupportTicket.grade_number.in_(grades))
        if subjects is not None:
            parts.append(SupportTicket.subject_code.in_(subjects))
        clauses.append(and_(*parts))
    return or_(*clauses) if clauses else false()


def staff_queue(db: Session, who: Principal, *, status: str | None, category: str | None) -> list[SupportTicket]:
    stmt = select(SupportTicket).order_by(SupportTicket.updated_at.desc()).limit(200)
    if not _is_support(who):
        stmt = stmt.where(_reviewer_scope_clause(db, who))
    if status:
        stmt = stmt.where(SupportTicket.status == status)
    if category:
        stmt = stmt.where(SupportTicket.category == category)
    return list(db.scalars(stmt))


def staff_ticket(db: Session, who: Principal, ticket_id: uuid.UUID) -> SupportTicket:
    t = db.get(SupportTicket, ticket_id)
    if t is None:
        raise NotFound("Request not found.")
    if _is_support(who):
        return t
    if (
        t.category == "academic_report"
        and t.grade_number
        and t.subject_code
        and Permission.review_content
        in permissions_for(roles_in_scope(db, who.user.id, t.grade_number, t.subject_code))
    ):
        return t
    raise NotFound("Request not found.")


def context(db: Session, who: Principal, t: SupportTicket) -> dict[str, Any]:
    """Minimal, redacted context: identity for support staff only; reviewers see the question, not the person."""
    out: dict[str, Any] = {"learner": None, "plan": None, "question": None}
    if _is_support(who):
        user = db.get(AppUser, t.user_id)
        trial = access.trial_status(db, t.user_id)
        out["learner"] = {"email": user.email if user else None}
        out["plan"] = {
            "trial": trial["status"],
            "trial_ends_at": trial["ends_at"],
            "has_access": bool(access.active_entitlements(db, t.user_id, _now(db))),
        }
        record(
            db,
            actor=who.user.id,
            action="support.context_viewed",
            target_type="support_ticket",
            target_id=str(t.id),
            details={"learner": str(t.user_id)},
        )
        db.commit()
    if t.content_item_id and t.content_version_id:
        item = db.get(ContentItem, t.content_item_id)
        version = db.get(ContentVersion, t.content_version_id)
        if item and version:
            out["question"] = {
                "item_id": str(item.id),
                "title": item.title,
                "kind": item.kind,
                "version": version.number,
                "availability": item.availability,
                "quarantine_level": item.quarantine_level,
            }
    return out


def staff_reply(
    db: Session, who: Principal, ticket_id: uuid.UUID, body: str, *, internal: bool, status: str | None
) -> SupportTicket:
    t = staff_ticket(db, who, ticket_id)
    now = _now(db)
    db.add(
        SupportMessage(
            ticket_id=t.id, author_id=who.user.id, from_staff=True, internal=internal, body=body.strip(), created_at=now
        )
    )
    if status:
        t.status = status
    elif not internal and t.status == "open":
        t.status = "waiting_learner"
    t.updated_at = now
    record(
        db,
        actor=who.user.id,
        action="support.replied" + (".internal" if internal else ""),
        target_type="support_ticket",
        target_id=str(t.id),
        details={"status": t.status},
    )
    db.commit()
    db.refresh(t)
    return t
