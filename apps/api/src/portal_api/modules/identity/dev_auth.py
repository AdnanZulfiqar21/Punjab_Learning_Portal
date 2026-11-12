"""Development/test-only shortcuts on the portal's password issuer (AUTH-PASSWORD-01).

Mounted only when PORTAL_DEV_AUTH_ENABLED is true, which the startup validator forbids in staging/production.
`register` creates an already verified account (no email code), `token` can assert a second factor for testing
MFA-gated operations, and `last-code` reads the newest code the development outbox recorded for an address, so
end-to-end tests can complete the real verification flow. Responses are enumeration-safe like the real ones.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from portal_api import email as email_transport
from portal_api.config import get_settings
from portal_api.db import get_session
from portal_api.errors import Unauthorized
from portal_api.modules.identity.models import AppUser, PasswordCredential
from portal_api.modules.identity.schemas import DevRegisterIn, DevTokenIn, TokenOut
from portal_api.modules.identity.tokens import get_local_issuer

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
    exists = db.scalar(select(PasswordCredential.user_id).where(PasswordCredential.email == email))
    if exists is None:
        issuer = get_settings().password_auth_issuer
        try:
            user = AppUser(
                issuer=issuer, subject=f"dev|{email}", email=email, phone=body.phone, display_name=body.display_name
            )
            db.add(user)
            db.flush()
            db.execute(
                insert(PasswordCredential)
                .values(user_id=user.id, email=email, password_hash=password_hash, email_verified_at=func.now())
                .on_conflict_do_nothing(index_elements=["email"])
            )
            db.commit()
        except IntegrityError:  # a concurrent registration of the same email won; same generic answer
            db.rollback()
    return {"status": "accepted", "detail": "If this email can be registered, the account is ready to sign in."}


@router.post("/token", response_model=TokenOut, summary="Exchange development credentials for an access token")
def token(body: DevTokenIn, db: DB, response: Response) -> TokenOut:
    response.headers["Cache-Control"] = "no-store"
    cred = db.scalar(select(PasswordCredential).where(PasswordCredential.email == body.email.lower()))
    stored = cred.password_hash if cred else _DUMMY_HASH
    db.rollback()  # return the connection to the pool before the slow verify (R08)
    try:
        _hasher.verify(stored, body.password)
    except VerificationError as e:
        raise Unauthorized("Email or password is incorrect.") from e
    if cred is None:
        raise Unauthorized("Email or password is incorrect.")
    user = db.get(AppUser, cred.user_id)
    if user is None or user.status != "active" or cred.email_verified_at is None:
        raise Unauthorized("Email or password is incorrect.")
    issuer = get_local_issuer()
    return TokenOut(access_token=issuer.issue(user.subject, user.email, mfa=body.mfa), expires_in=issuer.ttl_s)


class LastCodeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    purpose: Literal["verify-email", "reset-password"] = "verify-email"


_CODE = re.compile(r"\b(\d{6})\b")


@router.post("/last-code", summary="Development only: the newest verification code the dev outbox sent to an address")
def last_code(body: LastCodeIn) -> dict[str, str | None]:
    address = body.email.lower()
    for entry in reversed(email_transport.outbox()):
        if entry.message.to.lower() == address and entry.message.tag == body.purpose:
            found = _CODE.search(entry.message.text)
            return {"code": found.group(1) if found else None}
    return {"code": None}
