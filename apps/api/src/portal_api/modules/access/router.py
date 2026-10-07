"""Learner access status, trial activation and staff-granted entitlements (P14.S1/S5, W08.S1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.db import get_session
from portal_api.errors import NotFound
from portal_api.modules.access import service
from portal_api.modules.access.models import Entitlement
from portal_api.modules.identity.deps import CurrentPrincipal, Principal, require
from portal_api.modules.identity.models import AppUser
from portal_api.modules.identity.permissions import Permission

router = APIRouter(prefix="/v1", tags=["access"])
DB = Annotated[Session, Depends(get_session)]
Granter = Annotated[Principal, Depends(require(Permission.grant_entitlements))]


class EntitlementOut(BaseModel):
    id: uuid.UUID
    source: Literal["trial", "paid", "scholarship", "promotional", "pilot"]
    starts_at: datetime
    ends_at: datetime
    status: Literal["active", "revoked", "refunded"]
    written_units: int


class TrialOut(BaseModel):
    program: str
    eligible: bool
    status: Literal["available", "not_eligible", "active", "ended", "converted", "revoked"]
    granted_at: datetime | None
    ends_at: datetime | None
    reason: str | None


class AllowanceOut(BaseModel):
    granted: int
    reserved: int
    accepted: int
    consumed: int
    available: int


class AccessOut(BaseModel):
    has_access: bool = Field(description="True when a current entitlement allows new practice and written tests")
    entitlements: list[EntitlementOut]
    trial: TrialOut
    written_allowance: AllowanceOut
    weights: dict[str, int] = Field(description="Written allowance units per question type")
    device_check: str = Field(description="How the trial decision was made on this platform")


class GrantIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    source: Literal["scholarship", "promotional", "pilot"]
    days: int = Field(ge=1, le=366)
    written_units: int = Field(ge=0, le=500)
    reason: str = Field(min_length=10, max_length=1000)


class RevokeIn(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)


def _ent(e: Entitlement) -> EntitlementOut:
    return EntitlementOut(
        id=e.id,
        source=e.source,  # type: ignore[arg-type]
        starts_at=e.starts_at,
        ends_at=e.ends_at,
        status=e.status,  # type: ignore[arg-type]
        written_units=e.written_units,
    )


def _access(db: Session, user_id: uuid.UUID) -> AccessOut:
    now = service.db_now(db)
    ents = list(db.scalars(select(Entitlement).where(Entitlement.user_id == user_id).order_by(Entitlement.created_at)))
    return AccessOut(
        has_access=bool(service.active_entitlements(db, user_id, now)),
        entitlements=[_ent(e) for e in ents],
        trial=TrialOut(**service.trial_status(db, user_id)),
        written_allowance=AllowanceOut(**service.allowance(db, user_id)),
        weights=service.QUESTION_WEIGHTS,
        device_check="Account history only; device recognition is not available yet.",
    )


@router.get("/me/access", response_model=AccessOut, summary="Plans, trial status and written allowance")
def my_access(db: DB, who: CurrentPrincipal, response: Response) -> AccessOut:
    response.headers["Cache-Control"] = "private, no-store"
    return _access(db, who.user.id)


@router.post("/me/trial", response_model=AccessOut, summary="Start the one-time 30-day free trial (idempotent)")
def start_trial(
    db: DB,
    who: CurrentPrincipal,
    response: Response,
    client: Annotated[Literal["web", "native"], Header(alias="X-Portal-Client")] = "web",
) -> AccessOut:
    response.headers["Cache-Control"] = "private, no-store"
    service.start_trial(db, who.user.id, client=client)
    return _access(db, who.user.id)


@router.post(
    "/admin/entitlements",
    response_model=EntitlementOut,
    status_code=201,
    summary="Grant scholarship, promotional or pilot access (audited, MFA)",
)
def grant(db: DB, who: Granter, body: GrantIn) -> EntitlementOut:
    user = db.scalar(select(AppUser).where(AppUser.email == body.email.lower()))
    if user is None:
        raise NotFound("No account with that email.")
    return _ent(
        service.grant_entitlement(
            db,
            who.user.id,
            user.id,
            source=body.source,
            days=body.days,
            written_units=body.written_units,
            reason=body.reason,
        )
    )


@router.post(
    "/admin/entitlements/{entitlement_id}/revoke",
    response_model=EntitlementOut,
    summary="Revoke an entitlement (recorded, never deleted)",
)
def revoke(db: DB, who: Granter, entitlement_id: uuid.UUID, body: RevokeIn) -> EntitlementOut:
    return _ent(service.revoke_entitlement(db, who.user.id, entitlement_id, body.reason))
