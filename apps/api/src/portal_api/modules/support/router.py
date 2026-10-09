"""Support ticket API for learners and staff (P15.S3)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from portal_api.db import get_session
from portal_api.errors import Forbidden
from portal_api.modules.identity.deps import CurrentPrincipal, Principal
from portal_api.modules.identity.permissions import Permission
from portal_api.modules.support import service
from portal_api.modules.support.models import SupportMessage, SupportTicket

router = APIRouter(prefix="/v1", tags=["support"])
DB = Annotated[Session, Depends(get_session)]
Category = Literal["account", "access", "technical", "academic_report", "other"]
Status = Literal["open", "in_progress", "waiting_learner", "resolved"]


def staff_member(principal: CurrentPrincipal) -> Principal:
    if not principal.permissions & {Permission.view_support_context, Permission.review_content}:
        raise Forbidden("Support tools are for support staff and subject reviewers.")
    return principal


Staff = Annotated[Principal, Depends(staff_member)]


class ReferenceIn(BaseModel):
    kind: Literal["attempt", "written_attempt"]
    id: uuid.UUID
    position: int | None = Field(default=None, ge=1, le=200)


class TicketIn(BaseModel):
    category: Category
    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=5, max_length=4000)
    reference: ReferenceIn | None = None


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class StaffMessageIn(MessageIn):
    internal: bool = False
    status: Status | None = None


class MessageOut(BaseModel):
    from_staff: bool
    body: str
    created_at: datetime


class StaffMessageOut(MessageOut):
    internal: bool


class AttachmentOut(BaseModel):
    id: uuid.UUID
    width: int
    height: int
    size: int
    created_at: datetime


class TicketOut(BaseModel):
    id: uuid.UUID
    category: Category
    subject: str
    status: Status
    reference: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut]
    attachments: list[AttachmentOut] = Field(default_factory=list, description="Screenshots you added")


class StaffTicketOut(BaseModel):
    id: uuid.UUID
    category: Category
    subject: str
    status: Status
    reference: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    messages: list[StaffMessageOut]
    attachments: list[AttachmentOut] = Field(default_factory=list)
    context: dict[str, Any]
    escalated_at: datetime | None = None
    escalation_reason: str | None = None


class EscalateIn(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)


def _learner_view(db: Session, t: SupportTicket) -> TicketOut:
    msgs = service.messages(db, t, include_internal=False)
    return TicketOut(
        id=t.id,
        category=t.category,  # type: ignore[arg-type]
        subject=t.subject,
        status=t.status,  # type: ignore[arg-type]
        reference=t.reference,
        created_at=t.created_at,
        updated_at=t.updated_at,
        messages=[MessageOut(from_staff=m.from_staff, body=m.body, created_at=m.created_at) for m in msgs],
        attachments=_attachments(db, t),
    )


def _attachments(db: Session, t: SupportTicket) -> list[AttachmentOut]:
    return [
        AttachmentOut(id=a.id, width=a.width, height=a.height, size=a.size, created_at=a.created_at)
        for a in service.attachments(db, t.id)
    ]


def _staff_view(db: Session, who: Principal, t: SupportTicket, *, with_context: bool = True) -> StaffTicketOut:
    msgs: list[SupportMessage] = service.messages(db, t, include_internal=True)
    return StaffTicketOut(
        id=t.id,
        category=t.category,  # type: ignore[arg-type]
        subject=t.subject,
        status=t.status,  # type: ignore[arg-type]
        reference=t.reference,
        created_at=t.created_at,
        updated_at=t.updated_at,
        messages=[
            StaffMessageOut(from_staff=m.from_staff, internal=m.internal, body=m.body, created_at=m.created_at)
            for m in msgs
        ],
        attachments=_attachments(db, t),
        context=service.context(db, who, t) if with_context else {},
        escalated_at=t.escalated_at,
        escalation_reason=t.escalation_reason,
    )


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@router.post("/support/tickets", response_model=TicketOut, status_code=201, summary="Ask for help or report a question")
def create(db: DB, who: CurrentPrincipal, body: TicketIn, response: Response) -> TicketOut:
    _private(response)
    t = service.create_ticket(
        db,
        who,
        category=body.category,
        subject=body.subject,
        body=body.body,
        reference=body.reference.model_dump(mode="json") if body.reference else None,
    )
    return _learner_view(db, t)


@router.get("/support/tickets", response_model=list[TicketOut])
def mine(db: DB, who: CurrentPrincipal, response: Response) -> list[TicketOut]:
    _private(response)
    return [_learner_view(db, t) for t in service.my_tickets(db, who)]


@router.get("/support/tickets/{ticket_id}", response_model=TicketOut)
def one(db: DB, who: CurrentPrincipal, ticket_id: uuid.UUID, response: Response) -> TicketOut:
    _private(response)
    return _learner_view(db, service.own_ticket(db, who, ticket_id))


@router.post("/support/tickets/{ticket_id}/messages", response_model=TicketOut)
def reply(db: DB, who: CurrentPrincipal, ticket_id: uuid.UUID, body: MessageIn, response: Response) -> TicketOut:
    _private(response)
    return _learner_view(db, service.learner_reply(db, who, ticket_id, body.body))


@router.get("/staff/support/tickets", response_model=list[StaffTicketOut], summary="Support queue (scoped)")
def staff_queue(
    db: DB,
    who: Staff,
    response: Response,
    status: Annotated[Status | None, Query()] = None,
    category: Annotated[Category | None, Query()] = None,
) -> list[StaffTicketOut]:
    _private(response)
    return [
        _staff_view(db, who, t, with_context=False)
        for t in service.staff_queue(db, who, status=status, category=category)
    ]


@router.get("/staff/support/tickets/{ticket_id}", response_model=StaffTicketOut)
def staff_one(db: DB, who: Staff, ticket_id: uuid.UUID, response: Response) -> StaffTicketOut:
    _private(response)
    return _staff_view(db, who, service.staff_ticket(db, who, ticket_id))


@router.post("/staff/support/tickets/{ticket_id}/messages", response_model=StaffTicketOut)
def staff_reply(db: DB, who: Staff, ticket_id: uuid.UUID, body: StaffMessageIn, response: Response) -> StaffTicketOut:
    _private(response)
    t = service.staff_reply(db, who, ticket_id, body.body, internal=body.internal, status=body.status)
    return _staff_view(db, who, t)


@router.post(
    "/staff/support/tickets/{ticket_id}/escalate",
    response_model=StaffTicketOut,
    summary="Escalate for senior attention (staff note; audited; listed first)",
)
def escalate(db: DB, who: Staff, ticket_id: uuid.UUID, body: EscalateIn, response: Response) -> StaffTicketOut:
    _private(response)
    return _staff_view(db, who, service.escalate(db, who, ticket_id, body.reason))


@router.post(
    "/support/tickets/{ticket_id}/attachments",
    response_model=AttachmentOut,
    status_code=201,
    summary="Add a screenshot (raw JPEG or PNG, at most 5 MB); it is validated and re-encoded in isolation",
)
async def add_screenshot(
    db: DB, who: CurrentPrincipal, ticket_id: uuid.UUID, request: Request, response: Response
) -> AttachmentOut:
    from starlette.concurrency import run_in_threadpool

    from portal_api.errors import TooLarge

    _private(response)
    buf = bytearray()
    async for chunk in request.stream():
        buf.extend(chunk)
        if len(buf) > service.MAX_SCREENSHOT_BYTES:
            raise TooLarge("Screenshots can be at most 5 MB.")
    a = await run_in_threadpool(service.add_screenshot, db, who, ticket_id, bytes(buf))
    return AttachmentOut(id=a.id, width=a.width, height=a.height, size=a.size, created_at=a.created_at)


@router.get("/support/tickets/{ticket_id}/attachments/{attachment_id}", summary="A screenshot (owner or scoped staff)")
def get_screenshot(db: DB, who: CurrentPrincipal, ticket_id: uuid.UUID, attachment_id: uuid.UUID) -> Response:
    data = service.screenshot_bytes(db, who, ticket_id, attachment_id)
    return Response(
        content=data,
        media_type="image/png",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )
