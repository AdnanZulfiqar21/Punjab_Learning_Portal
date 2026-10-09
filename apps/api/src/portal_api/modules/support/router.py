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
from portal_api.modules.identity.deps import CurrentPrincipal, Principal, require
from portal_api.modules.identity.permissions import Permission
from portal_api.modules.support import lookup, service
from portal_api.modules.support.models import SupportMessage, SupportTicket
from portal_api.modules.system import operations

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
    dependencies=[Depends(operations.requires("support_screenshots"))],
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


# ------------------------------------------------------------------ support lookup and assisted access (P15.S3.T3)
Lookup = Annotated[Principal, Depends(require(Permission.look_up_learners))]


class LookupIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class LearnerOut(BaseModel):
    id: uuid.UUID
    email: str | None
    display_name: str | None
    status: str
    created_at: datetime
    open_requests: int


class AssistIn(BaseModel):
    ticket_id: uuid.UUID = Field(description="One of the learner's open requests")
    reason: str = Field(min_length=10, max_length=500)
    minutes: int = Field(default=15, ge=5, le=lookup.MAX_ASSIST_MINUTES)


class AssistOut(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    reason: str
    granted_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class TimelineEventOut(BaseModel):
    at: datetime
    kind: str
    detail: dict[str, Any]


class TimelineOut(BaseModel):
    learner: LearnerOut
    assisted_access: AssistOut | None = Field(description="Your active assisted access, if any (adds result summaries)")
    events: list[TimelineEventOut]


def _learner_out(db: Session, u: Any) -> LearnerOut:
    return LearnerOut(
        id=u.id,
        email=u.email,
        display_name=u.display_name,
        status=u.status,
        created_at=u.created_at,
        open_requests=lookup.open_requests(db, u.id),
    )


def _assist_out(a: Any) -> AssistOut:
    return AssistOut(
        id=a.id,
        ticket_id=a.ticket_id,
        reason=a.reason,
        granted_at=a.granted_at,
        expires_at=a.expires_at,
        revoked_at=a.revoked_at,
    )


@router.post(
    "/staff/support/learners/lookup",
    response_model=LearnerOut,
    summary="Find a learner by exact email (support, MFA; audited)",
)
def find_learner(body: LookupIn, db: DB, who: Lookup, response: Response) -> LearnerOut:
    _private(response)
    return _learner_out(db, lookup.find_learner(db, who, body.email))


@router.get(
    "/staff/support/learners/{user_id}/timeline",
    response_model=TimelineOut,
    summary="A learner's redacted activity timeline, including trial decisions (support, MFA; audited)",
)
def learner_timeline(user_id: uuid.UUID, db: DB, who: Lookup, response: Response) -> TimelineOut:
    _private(response)
    user, assist, events = lookup.timeline(db, who, user_id)
    return TimelineOut(
        learner=_learner_out(db, user),
        assisted_access=_assist_out(assist) if assist else None,
        events=[TimelineEventOut(**e) for e in events],
    )


@router.post(
    "/staff/support/learners/{user_id}/assisted-access",
    response_model=AssistOut,
    status_code=201,
    summary="Start time-limited assisted access for one of the learner's open requests (learner is told; audited)",
)
def grant_assisted_access(user_id: uuid.UUID, body: AssistIn, db: DB, who: Lookup) -> AssistOut:
    return _assist_out(lookup.grant_assist(db, who, user_id, body.ticket_id, body.reason, body.minutes))


@router.delete("/staff/support/assisted-access/{access_id}", status_code=204, summary="End your assisted access")
def end_assisted_access(access_id: uuid.UUID, db: DB, who: Lookup) -> Response:
    lookup.revoke_assist(db, who, access_id, as_learner=False)
    return Response(status_code=204)


@router.get(
    "/me/assisted-access",
    response_model=list[AssistOut],
    summary="Times support had assisted access to your activity",
)
def my_assisted_access(db: DB, who: CurrentPrincipal, response: Response) -> list[AssistOut]:
    _private(response)
    return [_assist_out(a) for a in lookup.my_assists(db, who.user.id)]


@router.delete("/me/assisted-access/{access_id}", status_code=204, summary="End support's assisted access now")
def end_my_assisted_access(access_id: uuid.UUID, db: DB, who: CurrentPrincipal) -> Response:
    lookup.revoke_assist(db, who, access_id, as_learner=True)
    return Response(status_code=204)
