"""Audit explorer (roadmap P16.S4.T1; AUDIT-01).

Owner/admins with an MFA session (`view_audit`) filter the append-only audit trail by action (exact or prefix such as
`content.`), actor email, target and time, newest first, with keyset pagination. Sensitive payload values are
redacted. The trail itself cannot be edited or deleted: a database trigger refuses UPDATE and DELETE on
`audit_event`. Every search is itself audited.
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from portal_api.db import get_session
from portal_api.errors import Unprocessable
from portal_api.modules.audit.models import AuditEvent, record
from portal_api.modules.identity.deps import Principal, require
from portal_api.modules.identity.models import AppUser
from portal_api.modules.identity.permissions import Permission

router = APIRouter(prefix="/v1/admin", tags=["audit"])
DB = Annotated[Session, Depends(get_session)]
Auditor = Annotated[Principal, Depends(require(Permission.view_audit))]
_SENSITIVE = ("email", "token", "hash", "password", "secret", "destination", "ip", "phone")


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: "[redacted]" if any(s in k.lower() for s in _SENSITIVE) else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


class AuditRow(BaseModel):
    id: uuid.UUID
    at: datetime
    action: str
    actor: str | None
    target_type: str
    target_id: str
    details: dict[str, Any]
    correlation_id: str | None


class AuditPage(BaseModel):
    events: list[AuditRow]
    next_before: str | None


def _cursor(at: datetime, id_: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{at.isoformat()}|{id_}".encode()).decode()


def _parse_cursor(c: str) -> tuple[datetime, uuid.UUID]:
    try:
        at, id_ = base64.urlsafe_b64decode(c.encode()).decode().split("|")
        return datetime.fromisoformat(at), uuid.UUID(id_)
    except (ValueError, UnicodeDecodeError):
        raise Unprocessable("Invalid page cursor.") from None


@router.get("/audit", response_model=AuditPage, summary="Search the audit trail (owner/admin, MFA; redacted)")
def search(
    db: DB,
    who: Auditor,
    response: Response,
    action: Annotated[str | None, Query(max_length=80, description="Exact action, or a prefix ending in '.'")] = None,
    actor_email: Annotated[str | None, Query(max_length=320)] = None,
    target_type: Annotated[str | None, Query(max_length=40)] = None,
    target_id: Annotated[str | None, Query(max_length=80)] = None,
    since: datetime | None = None,
    until: datetime | None = None,
    before: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AuditPage:
    response.headers["Cache-Control"] = "private, no-store"
    q = select(AuditEvent, AppUser.email).outerjoin(AppUser, AppUser.id == AuditEvent.actor_user_id)
    if action:
        q = q.where(AuditEvent.action.startswith(action) if action.endswith(".") else AuditEvent.action == action)
    if actor_email:
        q = q.where(AppUser.email == actor_email.strip().lower())
    if target_type:
        q = q.where(AuditEvent.target_type == target_type)
    if target_id:
        q = q.where(AuditEvent.target_id == target_id)
    if since:
        q = q.where(AuditEvent.at >= since)
    if until:
        q = q.where(AuditEvent.at < until)
    if before:
        at, id_ = _parse_cursor(before)
        q = q.where(or_(AuditEvent.at < at, and_(AuditEvent.at == at, AuditEvent.id < id_)))
    rows = db.execute(q.order_by(AuditEvent.at.desc(), AuditEvent.id.desc()).limit(limit + 1)).all()
    more = len(rows) > limit
    rows = rows[:limit]
    events = [
        AuditRow(
            id=e.id,
            at=e.at,
            action=e.action,
            actor=email,
            target_type=e.target_type,
            target_id=e.target_id,
            details=redact(e.details or {}),
            correlation_id=e.correlation_id,
        )
        for e, email in rows
    ]
    record(
        db,
        actor=who.user.id,
        action="audit.searched",
        target_type="audit_event",
        target_id="-",
        details={
            "filters": {
                k: v for k, v in {"action": action, "target_type": target_type, "target_id": target_id}.items() if v
            },
            "actor_filter": bool(actor_email),
            "returned": len(events),
        },
    )
    db.commit()
    last = rows[-1][0] if rows else None
    return AuditPage(events=events, next_before=_cursor(last.at, last.id) if more and last else None)
