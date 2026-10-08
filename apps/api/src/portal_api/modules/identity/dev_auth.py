"""Development-only email/password issuer (stand-in for the managed OIDC provider, BLOCKERS B04).

Mounted only when PORTAL_DEV_AUTH_ENABLED is true, which the startup validator forbids in staging/production.
Responses are enumeration-safe: registration always answers the same way, and login failures are indistinguishable.
"""

from __future__ import annotations

from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from portal_api.config import get_settings
from portal_api.db import get_session
from portal_api.errors import Unauthorized
from portal_api.modules.identity.models import AppUser, DevCredential
from portal_api.modules.identity.schemas import DevRegisterIn, DevTokenIn, TokenOut
from portal_api.modules.identity.tokens import get_dev_issuer

router = APIRouter(prefix="/v1/dev-auth", tags=["dev-auth (development only)"], include_in_schema=False)
DB = Annotated[Session, Depends(get_session)]
_hasher = PasswordHasher()
# Verify against a real hash when the email is unknown, so timing doesn't reveal which accounts exist.
_DUMMY_HASH = _hasher.hash("not-a-real-password-placeholder")


@router.post("/register", status_code=202, summary="Create a development account (always 202)")
def register(body: DevRegisterIn, db: DB) -> dict[str, str]:
    email = body.email.lower()
    # Hash before touching the database: argon2 is deliberately slow, and holding a pooled connection during it
    # starved the pool under load (review R08).
    password_hash = _hasher.hash(body.password)
    exists = db.scalar(select(DevCredential.user_id).where(DevCredential.email == email))
    if exists is None:
        issuer = get_settings().dev_auth_issuer
        try:
            user = AppUser(issuer=issuer, subject=f"dev|{email}", email=email, display_name=body.display_name)
            db.add(user)
            db.flush()
            db.execute(
                insert(DevCredential)
                .values(user_id=user.id, email=email, password_hash=password_hash)
                .on_conflict_do_nothing(index_elements=["email"])
            )
            db.commit()
        except IntegrityError:  # a concurrent registration of the same email won; same generic answer
            db.rollback()
    return {"status": "accepted", "detail": "If this email can be registered, the account is ready to sign in."}


@router.post("/token", response_model=TokenOut, summary="Exchange development credentials for an access token")
def token(body: DevTokenIn, db: DB, response: Response) -> TokenOut:
    response.headers["Cache-Control"] = "no-store"
    cred = db.scalar(select(DevCredential).where(DevCredential.email == body.email.lower()))
    stored = cred.password_hash if cred else _DUMMY_HASH
    db.rollback()  # return the connection to the pool before the slow verify (R08)
    try:
        _hasher.verify(stored, body.password)
    except VerificationError as e:
        raise Unauthorized("Email or password is incorrect.") from e
    if cred is None:
        raise Unauthorized("Email or password is incorrect.")
    user = db.get(AppUser, cred.user_id)
    if user is None or user.status != "active":
        raise Unauthorized("Email or password is incorrect.")
    issuer = get_dev_issuer()
    return TokenOut(access_token=issuer.issue(user.subject, user.email, mfa=body.mfa), expires_in=issuer.ttl_s)
