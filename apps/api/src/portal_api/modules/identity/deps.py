"""FastAPI dependencies for authentication and authorisation (P04.S2.T1)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from portal_api.db import get_session
from portal_api.errors import Forbidden, Unauthorized
from portal_api.modules.identity import sessions, tokens
from portal_api.modules.identity.models import AppUser, StaffRoleGrant
from portal_api.modules.identity.permissions import MFA_REQUIRED, Permission, Role, permissions_for


@dataclass(frozen=True)
class Principal:
    user: AppUser
    claims: tokens.Claims
    roles: frozenset[Role]
    permissions: frozenset[Permission]
    session: sessions.UserSession | None = None  # set when authenticated with an application session token


def _bearer(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value:
        raise Unauthorized("Sign in to continue.")
    return value.strip()


EXPIRED = "Your session is invalid or has expired. Please sign in again."


def _from_session(db: Session, token: str) -> tuple[AppUser, tokens.Claims, sessions.UserSession]:
    row = sessions.resolve(db, token)
    if row is None:
        raise Unauthorized(EXPIRED)
    user = db.get(AppUser, row.user_id)
    if user is None:
        raise Unauthorized(EXPIRED)
    claims = tokens.Claims(
        issuer=user.issuer,
        subject=user.subject,
        email=user.email,
        token_id=str(row.id),
        expires_at=int(row.expires_at.timestamp()),
        mfa=row.mfa,
    )
    return user, claims, row


def current_principal(request: Request, db: Annotated[Session, Depends(get_session)]) -> Principal:
    token = _bearer(request)
    if token.startswith(sessions.PREFIX):
        session_user, session_claims, session_row = _from_session(db, token)
        if session_user.status != "active":
            raise Forbidden("This account is not active. Contact support.")
        return _principal(request, db, session_user, session_claims, session_row)
    try:
        claims = tokens.verify(token)
    except tokens.InvalidToken as e:
        raise Unauthorized(EXPIRED) from e
    user = db.scalar(select(AppUser).where(AppUser.issuer == claims.issuer, AppUser.subject == claims.subject))
    if user is None:
        # First authenticated request from a verified identity creates the application account (no trial is granted
        # or restarted here; trial eligibility is a separate server decision, roadmap §16). Concurrent first requests
        # are safe: the insert is idempotent on (issuer, subject).
        db.execute(
            insert(AppUser)
            .values(id=uuid.uuid4(), issuer=claims.issuer, subject=claims.subject, email=claims.email, status="active")
            .on_conflict_do_nothing(index_elements=["issuer", "subject"])
        )
        db.commit()
        user = db.scalars(
            select(AppUser).where(AppUser.issuer == claims.issuer, AppUser.subject == claims.subject)
        ).one()
    if user.status != "active":
        raise Forbidden("This account is not active. Contact support.")
    user.last_seen_at = datetime.now(UTC)
    if claims.email and user.email != claims.email:
        user.email = claims.email
    db.commit()
    return _principal(request, db, user, claims, None)


def _principal(
    request: Request, db: Session, user: AppUser, claims: tokens.Claims, session_row: sessions.UserSession | None
) -> Principal:
    grants = db.scalars(
        select(StaffRoleGrant.role).where(StaffRoleGrant.user_id == user.id, StaffRoleGrant.revoked_at.is_(None))
    ).all()
    roles = frozenset(Role(r) for r in grants)
    request.state.user_id = user.id
    return Principal(
        user=user, claims=claims, roles=roles, permissions=permissions_for(set(roles)), session=session_row
    )


CurrentPrincipal = Annotated[Principal, Depends(current_principal)]


def optional_principal(request: Request, db: Annotated[Session, Depends(get_session)]) -> Principal | None:
    """The caller if they sent credentials, else None. Invalid credentials are still a 401, never anonymous."""
    if not request.headers.get("authorization"):
        return None
    return current_principal(request, db)


OptionalPrincipal = Annotated[Principal | None, Depends(optional_principal)]


def require(permission: Permission) -> Callable[[Principal], Principal]:
    """Dependency factory: the caller must hold `permission`, with an MFA session where the matrix requires it."""

    def check(principal: CurrentPrincipal) -> Principal:
        if permission not in principal.permissions:
            raise Forbidden("You don't have permission to do this.")
        if permission in MFA_REQUIRED and not principal.claims.mfa:
            raise Forbidden("This action needs a multi-factor authenticated session. Sign in again with MFA.")
        return principal

    return check
