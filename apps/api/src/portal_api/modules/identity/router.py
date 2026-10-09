"""Account, profile, consent and role-administration endpoints (P04.S1-S4)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.db import get_session
from portal_api.errors import Conflict, Forbidden, NotFound
from portal_api.modules.audit.models import record
from portal_api.modules.identity import sessions
from portal_api.modules.identity.deps import CurrentPrincipal, Principal, require
from portal_api.modules.identity.models import AppUser, ConsentRecord, StaffRoleGrant, StudentProfile
from portal_api.modules.identity.permissions import STAFF_ROLES, Permission
from portal_api.modules.identity.schemas import (
    ConsentIn,
    ConsentOut,
    MeOut,
    ProfileIn,
    ProfileOut,
    RevokeIn,
    RoleGrantIn,
    RoleGrantOut,
    SessionCreatedOut,
    SessionCreateIn,
    SessionOut,
)

router = APIRouter(prefix="/v1", tags=["identity"])
DB = Annotated[Session, Depends(get_session)]
PRIVATE = "private, no-store"


def _me(db: Session, principal: Principal) -> MeOut:
    user = principal.user
    profile = db.get(StudentProfile, user.id)
    consents = db.scalars(
        select(ConsentRecord).where(ConsentRecord.user_id == user.id).order_by(ConsentRecord.accepted_at)
    ).all()
    return MeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        roles=sorted(principal.roles),
        mfa_session=principal.claims.mfa,
        profile=ProfileOut.model_validate(profile) if profile else None,
        consents=[ConsentOut.model_validate(c) for c in consents],
    )


@router.get("/me", response_model=MeOut, summary="The signed-in account, its roles, profile and consents")
def me(principal: CurrentPrincipal, db: DB, response: Response) -> MeOut:
    response.headers["Cache-Control"] = PRIVATE
    return _me(db, principal)


@router.put("/me/profile", response_model=ProfileOut, summary="Save onboarding/learning preferences")
def put_profile(
    body: ProfileIn,
    principal: Annotated[Principal, Depends(require(Permission.edit_own_profile))],
    db: DB,
    response: Response,
) -> ProfileOut:
    response.headers["Cache-Control"] = PRIVATE
    profile = db.get(StudentProfile, principal.user.id)
    if profile is None:
        profile = StudentProfile(user_id=principal.user.id)
        db.add(profile)
    for field, value in body.model_dump().items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return ProfileOut.model_validate(profile)


@router.post("/me/consents", response_model=ConsentOut, status_code=201, summary="Accept a versioned document")
def accept_consent(body: ConsentIn, principal: CurrentPrincipal, db: DB) -> ConsentOut:
    existing = db.scalar(
        select(ConsentRecord).where(
            ConsentRecord.user_id == principal.user.id,
            ConsentRecord.document == body.document,
            ConsentRecord.version == body.version,
            ConsentRecord.withdrawn_at.is_(None),
        )
    )
    if existing:  # idempotent: accepting the same version twice returns the original record
        return ConsentOut.model_validate(existing)
    rec = ConsentRecord(user_id=principal.user.id, document=body.document, version=body.version)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return ConsentOut.model_validate(rec)


@router.delete("/me/consents/{document}", status_code=204, summary="Withdraw an optional consent")
def withdraw_consent(document: str, principal: CurrentPrincipal, db: DB) -> Response:
    if document in ("terms", "privacy"):
        raise Conflict("Terms and privacy acceptance can only end by closing the account (account deletion flow).")
    rows = db.scalars(
        select(ConsentRecord).where(
            ConsentRecord.user_id == principal.user.id,
            ConsentRecord.document == document,
            ConsentRecord.withdrawn_at.is_(None),
        )
    ).all()
    for r in rows:
        r.withdrawn_at = datetime.now(UTC)
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------- staff role administration (owner/admin, MFA)
ManageRoles = Annotated[Principal, Depends(require(Permission.manage_roles))]


@router.get("/admin/users/{user_id}/roles", response_model=list[RoleGrantOut], tags=["admin"])
def list_roles(user_id: uuid.UUID, _admin: ManageRoles, db: DB) -> list[RoleGrantOut]:
    if db.get(AppUser, user_id) is None:
        raise NotFound("User not found.")
    grants = db.scalars(
        select(StaffRoleGrant).where(StaffRoleGrant.user_id == user_id).order_by(StaffRoleGrant.granted_at)
    ).all()
    return [RoleGrantOut.model_validate(g) for g in grants]


@router.post("/admin/users/{user_id}/roles", response_model=RoleGrantOut, status_code=201, tags=["admin"])
def grant_role(user_id: uuid.UUID, body: RoleGrantIn, admin: ManageRoles, db: DB, request: Request) -> RoleGrantOut:
    if body.role not in STAFF_ROLES:
        raise Conflict("Only staff roles can be granted.")
    if user_id == admin.user.id:
        raise Forbidden("You can't change your own roles; ask another administrator.")
    target = db.get(AppUser, user_id)
    if target is None:
        raise NotFound("User not found.")
    if target.status != "active":
        raise Conflict("Roles can only be granted to active accounts.")
    active = db.scalar(
        select(StaffRoleGrant).where(
            StaffRoleGrant.user_id == user_id,
            StaffRoleGrant.role == body.role.value,
            StaffRoleGrant.revoked_at.is_(None),
        )
    )
    if active and active.scope == body.scope:
        return RoleGrantOut.model_validate(active)
    grant = StaffRoleGrant(
        user_id=user_id, role=body.role.value, scope=body.scope, granted_by=admin.user.id, reason=body.reason
    )
    db.add(grant)
    db.flush()
    record(
        db,
        actor=admin.user.id,
        action="role.grant",
        target_type="app_user",
        target_id=str(user_id),
        details={"grant_id": str(grant.id), "role": body.role.value, "scope": body.scope, "reason": body.reason},
        correlation_id=getattr(request.state, "correlation_id", None),
    )
    db.commit()
    db.refresh(grant)
    return RoleGrantOut.model_validate(grant)


@router.post("/admin/role-grants/{grant_id}/revoke", response_model=RoleGrantOut, tags=["admin"])
def revoke_role(grant_id: uuid.UUID, body: RevokeIn, admin: ManageRoles, db: DB, request: Request) -> RoleGrantOut:
    grant = db.get(StaffRoleGrant, grant_id)
    if grant is None:
        raise NotFound("Role grant not found.")
    if grant.user_id == admin.user.id:
        raise Forbidden("You can't change your own roles; ask another administrator.")
    if grant.revoked_at is None:
        grant.revoked_at = datetime.now(UTC)
        grant.revoked_by = admin.user.id
        grant.revoke_reason = body.reason
        record(
            db,
            actor=admin.user.id,
            action="role.revoke",
            target_type="app_user",
            target_id=str(grant.user_id),
            details={"grant_id": str(grant.id), "role": grant.role, "reason": body.reason},
            correlation_id=getattr(request.state, "correlation_id", None),
        )
        db.commit()
        db.refresh(grant)
    return RoleGrantOut.model_validate(grant)


# ---------------------------------------------------------------- sessions (P04.S1.T2/T3)
@router.post("/sessions", response_model=SessionCreatedOut, status_code=201, tags=["sessions"])
def create_session(
    body: SessionCreateIn, principal: CurrentPrincipal, db: DB, request: Request, response: Response
) -> SessionCreatedOut:
    """Exchange a verified identity-provider access token for a revocable application session."""
    response.headers["Cache-Control"] = "no-store"
    if principal.session is not None:
        raise Forbidden("A session cannot create another session; sign in with the identity provider.")
    row, token = sessions.create(
        db,
        user_id=principal.user.id,
        kind=body.kind,
        mfa=principal.claims.mfa,
        device_label=body.device_label,
        user_agent=request.headers.get("User-Agent"),
    )
    db.commit()
    return SessionCreatedOut(session_token=token, session=SessionOut.model_validate(row))


@router.get("/me/sessions", response_model=list[SessionOut], tags=["sessions"])
def list_sessions(principal: CurrentPrincipal, db: DB, response: Response) -> list[SessionOut]:
    response.headers["Cache-Control"] = PRIVATE
    rows = db.scalars(
        select(sessions.UserSession)
        .where(sessions.UserSession.user_id == principal.user.id, sessions.UserSession.revoked_at.is_(None))
        .order_by(sessions.UserSession.last_seen_at.desc())
    ).all()
    now = datetime.now(UTC)
    current_id = principal.session.id if principal.session else None
    return [
        SessionOut.model_validate(r).model_copy(update={"current": r.id == current_id})
        for r in rows
        if r.expires_at > now
    ]


@router.delete("/me/sessions/{session_id}", status_code=204, tags=["sessions"])
def revoke_session(session_id: uuid.UUID, principal: CurrentPrincipal, db: DB) -> Response:
    row = db.get(sessions.UserSession, session_id)
    if row is None or row.user_id != principal.user.id:  # never reveal other users' sessions
        raise NotFound("Session not found.")
    sessions.revoke(db, row, "user_revoked")
    db.commit()
    return Response(status_code=204)


@router.post("/me/sessions/revoke-others", status_code=204, tags=["sessions"])
def revoke_other_sessions(principal: CurrentPrincipal, db: DB) -> Response:
    keep = principal.session.id if principal.session else None
    for row in db.scalars(
        select(sessions.UserSession).where(
            sessions.UserSession.user_id == principal.user.id, sessions.UserSession.revoked_at.is_(None)
        )
    ):
        if row.id != keep:
            sessions.revoke(db, row, "user_revoked_others")
    db.commit()
    return Response(status_code=204)


@router.delete("/me/session", status_code=204, tags=["sessions"], summary="Sign out (revoke the current session)")
def sign_out(principal: CurrentPrincipal, db: DB) -> Response:
    if principal.session is None:
        raise Conflict("Not signed in with an application session.")
    sessions.revoke(db, principal.session, "signed_out")
    db.commit()
    return Response(status_code=204)


# ------------------------------------------------------------------ data access and deletion requests (P18.S3.T2)
class DeletionIn(BaseModel):
    confirm_email: str = Field(min_length=3, max_length=320)
    reason: str | None = Field(default=None, max_length=1000)


@router.get("/me/data-export", summary="Download the personal data the portal holds about you (JSON; audited)")
def data_export(db: Annotated[Session, Depends(get_session)], who: CurrentPrincipal) -> Response:
    from portal_api.modules.identity import privacy

    body, filename = privacy.export(db, who.user)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "private, no-store"},
    )


@router.post(
    "/me/deletion-request",
    status_code=202,
    summary="Ask for your account and data to be deleted (handled by support under the retention policy)",
)
def deletion_request(
    body: DeletionIn, db: Annotated[Session, Depends(get_session)], who: CurrentPrincipal
) -> dict[str, str]:
    from portal_api.modules.identity import privacy

    return {"ticket_id": str(privacy.request_deletion(db, who.user, body.confirm_email, body.reason))}
