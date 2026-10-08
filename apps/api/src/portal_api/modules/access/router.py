"""Learner access status, trial activation and staff-granted entitlements (P14.S1/S5, W08.S1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.db import get_session
from portal_api.errors import Conflict, NotFound, Unprocessable
from portal_api.modules.access import service, trial_devices
from portal_api.modules.access.models import Entitlement, TrialGrant
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
    device_state: Literal["device_authorization_required"] | None = Field(
        description="Set when this app installation must be added to the trial before protected trial use"
    )


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
        device_check=(
            "Web uses account history. Apps record device evidence; Apple and Google device checks aren't connected "
            "yet, so app trials currently rely on account history too."
            if trial_devices.evidence_mode() == "fallback"
            else "Apps need verified device evidence before a trial can start on a device."
        ),
        device_state=service.device_gate(db, user_id),  # type: ignore[arg-type]
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
    if client == "native":
        raise Unprocessable("Apps activate the trial through /v1/me/trial/claims with their installation token.")
    decision = trial_devices.claim(
        db, who.user.id, surface="web", idempotency_key="web-default", proof={}, install_token=None
    )
    if decision.state == "prior_paid":
        raise Conflict(decision.message)
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


class RemedyIn(BaseModel):
    attempt_id: uuid.UUID
    position: int | None = Field(default=None, ge=1, le=50, description="The affected question, if one")
    units: int = Field(ge=1, le=20)
    reason: str = Field(min_length=10, max_length=1000)
    defect_ref: str = Field(min_length=3, max_length=120, description="Incident, support request or case reference")
    idempotency_key: str = Field(min_length=8, max_length=80)


class RemedyOut(BaseModel):
    id: uuid.UUID
    attempt_id: uuid.UUID
    position: int | None
    units: int
    created_at: datetime


@router.post(
    "/staff/written-remedies",
    response_model=RemedyOut,
    summary="Credit written allowance for a service defect (separate idempotent event; MFA, audited)",
)
def remedy(db: DB, who: Granter, body: RemedyIn, response: Response) -> RemedyOut:
    response.headers["Cache-Control"] = "private, no-store"
    e = service.remedy_credit(
        db,
        who.user.id,
        attempt_id=body.attempt_id,
        position=body.position,
        units=body.units,
        reason=body.reason,
        defect_ref=body.defect_ref,
        idempotency_key=body.idempotency_key,
    )
    return RemedyOut(id=e.id, attempt_id=e.attempt_id, position=e.position, units=e.units, created_at=e.created_at)


# ------------------------------------------------------------------ trial claims and devices (roadmap §16; R06)
InstallHeader = Annotated[str | None, Header(alias="X-Portal-Install", description="Opaque per-install token")]
Reviewer = Annotated[Principal, Depends(require(Permission.review_trial_eligibility))]


class ClaimIn(BaseModel):
    surface: Literal["web", "ios", "android"]
    idempotency_key: str = Field(min_length=8, max_length=80)
    proof: dict[str, Any] = Field(
        default_factory=dict, description="Provider evidence (DeviceCheck/App Attest or Play Integrity), when available"
    )
    label: str = Field(default="", max_length=80, description="A name the learner recognises, e.g. 'My phone'")


class DeviceIn(BaseModel):
    surface: Literal["web", "ios", "android"]
    proof: dict[str, Any] = Field(default_factory=dict)
    label: str = Field(default="", max_length=80)
    replaces: uuid.UUID | None = Field(default=None, description="Self-service replacement of a registered device")


class TrialDecisionOut(BaseModel):
    state: Literal[
        "eligible",
        "granted",
        "active",
        "device_authorized",
        "paid_active",
        "account_trial_used",
        "prior_paid",
        "device_used",
        "review_required",
        "verification_pending",
        "device_limit",
    ]
    message: str = Field(description="The notice to show (roadmap §16.5)")
    claim_status: str | None
    ends_at: datetime | None = Field(description="The trial's original end; never extended by a device decision")
    device_id: uuid.UUID | None
    evidence: str | None = Field(description="What device evidence was available, e.g. provider_unconfigured")


class TrialDeviceOut(BaseModel):
    id: uuid.UUID
    surface: str
    label: str
    method: Literal["first_use", "recovery", "exception", "fallback", "web"]
    authorized_at: datetime
    this_device: bool


class ExceptionIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    surface: Literal["web", "ios", "android"]
    days: int = Field(ge=1, le=30)
    reason: str = Field(min_length=10, max_length=1000)


def _decision_out(d: trial_devices.Decision) -> TrialDecisionOut:
    ev = None
    src = d.device.evidence if d.device is not None else (d.claim.evidence if d.claim is not None else None)
    if src:
        ev = str(src.get("detail") or src.get("verdict") or "")
    return TrialDecisionOut(
        state=d.state,  # type: ignore[arg-type]
        message=d.message,
        claim_status=d.claim.status if d.claim else None,
        ends_at=d.grant.ends_at if d.grant else None,
        device_id=d.device.id if d.device else None,
        evidence=ev,
    )


@router.post(
    "/me/trial/claims",
    response_model=TrialDecisionOut,
    summary="Activate or recover the one free trial for this account (idempotent per key; roadmap §16.2/16.4)",
)
def trial_claim(
    db: DB, who: CurrentPrincipal, body: ClaimIn, response: Response, install: InstallHeader = None
) -> TrialDecisionOut:
    response.headers["Cache-Control"] = "private, no-store"
    return _decision_out(
        trial_devices.claim(
            db,
            who.user.id,
            surface=body.surface,
            idempotency_key=body.idempotency_key,
            proof=body.proof,
            install_token=install,
            label=body.label,
        )
    )


@router.post(
    "/me/trial/devices",
    response_model=TrialDecisionOut,
    summary="Authorize this device for your active trial (first trial use; limits and review apply)",
)
def trial_device(
    db: DB, who: CurrentPrincipal, body: DeviceIn, response: Response, install: InstallHeader = None
) -> TrialDecisionOut:
    response.headers["Cache-Control"] = "private, no-store"
    return _decision_out(
        trial_devices.authorize_device(
            db,
            who.user.id,
            surface=body.surface,
            proof=body.proof,
            install_token=install,
            label=body.label,
            replaces=body.replaces,
        )
    )


@router.get("/me/trial/devices", response_model=list[TrialDeviceOut], summary="Devices registered for your trial")
def trial_devices_list(
    db: DB, who: CurrentPrincipal, response: Response, install: InstallHeader = None
) -> list[TrialDeviceOut]:
    response.headers["Cache-Control"] = "private, no-store"
    grant = db.scalar(select(TrialGrant).where(TrialGrant.user_id == who.user.id))
    if grant is None:
        return []
    mine = trial_devices.installation_ref(install) if install else None
    return [
        TrialDeviceOut(
            id=d.id,
            surface=d.surface,
            label=d.label,
            method=d.method,  # type: ignore[arg-type]
            authorized_at=d.authorized_at,
            this_device=d.installation_ref == mine,
        )
        for d in trial_devices.active_devices(db, grant.id)
    ]


@router.delete("/me/trial/devices/{device_id}", status_code=204, summary="Remove a device from your trial")
def trial_device_remove(db: DB, who: CurrentPrincipal, device_id: uuid.UUID) -> Response:
    trial_devices.remove_device(db, who.user.id, device_id)
    return Response(status_code=204)


@router.post(
    "/staff/trial/exceptions",
    status_code=201,
    summary="Shared or second-hand device exception: account-scoped and time-bounded (support review, MFA, audited)",
)
def trial_exception(db: DB, who: Reviewer, body: ExceptionIn) -> dict[str, Any]:
    user = db.scalar(select(AppUser).where(AppUser.email == body.email.lower()))
    if user is None:
        raise NotFound("No account with that email.")
    exc = trial_devices.grant_exception(
        db, who.user.id, user.id, surface=body.surface, days=body.days, reason=body.reason
    )
    return {"id": str(exc.id), "expires_at": exc.expires_at.isoformat()}
