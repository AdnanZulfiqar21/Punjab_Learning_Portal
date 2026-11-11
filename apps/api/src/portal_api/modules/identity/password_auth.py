"""The portal's own email + password accounts with email verification (AUTH-PASSWORD-01, owner 2026-11-11).

Sign-up sends a 6-digit code to the address (Resend in deployed roles). The account can't sign in until the code is
entered, which proves the person owns the inbox. Entering it signs the person in. Then, as with any identity provider,
the client exchanges the short-lived access token for an application session (`POST /v1/sessions`).

Rules:
* Responses don't reveal which emails have accounts: registering always answers 202 and a wrong or unknown
  email/code pair is the same 400 (`INVALID_CODE`). Signing in with a correct password on an unverified account says
  so (403 `EMAIL_NOT_VERIFIED`), because only the password holder can learn it.
* A mobile number and date of birth are required (owner 2026-11-11); neither is verified. The phone is stored in
  E.164.
* Promotional emails need an explicit opt-in at sign-up (unticked by default), kept as a withdrawable
  `marketing_messages` consent.
* Registering again before verifying replaces the password and phone: only whoever reads the inbox can finish, so an
  earlier registration by someone else can't keep a password the owner doesn't know.
* A code lasts 15 minutes and allows 5 wrong tries. Only the newest code counts. New codes: one a minute and 5 an
  hour per account. Only a salted SHA-256 of a code is stored.
* No pooled connection is held while hashing a password or sending an email (review R08).
"""

from __future__ import annotations

import hashlib
import hmac
import html
import secrets
import uuid
from datetime import date, datetime, timedelta
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from portal_api import email
from portal_api.config import get_settings
from portal_api.db import get_session
from portal_api.errors import AppError, Forbidden, TooMany, Unauthorized, Unavailable
from portal_api.modules.audit.models import record
from portal_api.modules.identity.models import AppUser, ConsentRecord, EmailCode, PasswordCredential
from portal_api.modules.identity.schemas import TokenOut, check_date_of_birth, normalize_phone
from portal_api.modules.identity.tokens import get_local_issuer

router = APIRouter(prefix="/v1/auth", tags=["auth"])
DB = Annotated[Session, Depends(get_session)]
_hasher = PasswordHasher()
# Verify against a real hash when the email is unknown, so timing doesn't reveal which accounts exist.
_DUMMY_HASH = _hasher.hash("not-a-real-password-placeholder")

PURPOSE = "verify_email"
CODE_TTL = timedelta(minutes=15)
MAX_TRIES = 5
COOLDOWN = timedelta(seconds=60)
MAX_CODES_PER_HOUR = 5
ACCEPTED = "If this email can be registered, we have sent a 6-digit code to it."
# The wording shown beside the sign-up opt-in; a new wording needs a new version.
MARKETING_CONSENT_VERSION = "signup-2026-11-11"


class InvalidCode(AppError):
    status = 400
    code = "INVALID_CODE"


class EmailNotVerified(Forbidden):
    code = "EMAIL_NOT_VERIFIED"


class RegisterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    # Required (owner 2026-11-11), stored in E.164 and not verified.
    phone: str = Field(min_length=7, max_length=30, description="Mobile number, e.g. 0300 1234567 or +92 300 1234567")
    date_of_birth: date = Field(description="Required (owner 2026-11-11); not verified")
    # Promotional emails only with this explicit opt-in (unticked by default); recorded as a marketing_messages consent
    # the person can withdraw at any time.
    marketing_emails: bool = False
    display_name: str | None = Field(default=None, max_length=120)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)

    @field_validator("date_of_birth")
    @classmethod
    def _dob(cls, v: date) -> date:
        return check_date_of_birth(v)


class EmailIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class VerifyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    code: str = Field(pattern=r"^\s*\d{6}\s*$", description="The 6-digit code from the email")


class SignInIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class AcceptedOut(BaseModel):
    status: str = "accepted"
    detail: str


def _hash_code(code_id: uuid.UUID, code: str) -> str:
    return hashlib.sha256(f"{code_id}:{code}".encode()).hexdigest()


def _code_message(to: str, code: str) -> email.Message:
    text = (
        f"Your Sirf Concepts verification code is {code}.\n\n"
        "Enter it in the app to confirm your email. It expires in 15 minutes.\n"
        f"Aap ka Sirf Concepts verification code {code} hai. Yeh 15 minute tak chalega.\n\n"
        "If you didn't create an account, ignore this email; nothing will happen."
    )
    body = (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:480px;margin:auto;color:#1f2937">'
        '<h2 style="margin:0 0 12px">Sirf Concepts</h2>'
        "<p>Your verification code is:</p>"
        f'<p style="font-size:32px;font-weight:bold;letter-spacing:8px;margin:8px 0 16px">{html.escape(code)}</p>'
        "<p>Enter it in the app to confirm your email. It expires in 15 minutes.</p>"
        f'<p style="color:#4b5563">Aap ka verification code <b>{html.escape(code)}</b> hai. '
        "Yeh 15 minute tak chalega.</p>"
        '<p style="color:#6b7280;font-size:13px">If you didn\'t create an account, ignore this email; '
        "nothing will happen.</p></div>"
    )
    return email.Message(
        to=to, subject="Your Sirf Concepts verification code", text=text, html=body, tag="verify-email"
    )


def _set_marketing(db: Session, user_id: uuid.UUID, wanted: bool) -> None:
    """Before verification the latest sign-up form decides the opt-in (the same person may register again)."""
    active = db.scalars(
        select(ConsentRecord).where(
            ConsentRecord.user_id == user_id,
            ConsentRecord.document == "marketing_messages",
            ConsentRecord.withdrawn_at.is_(None),
        )
    ).all()
    if wanted and not active:
        db.add(ConsentRecord(user_id=user_id, document="marketing_messages", version=MARKETING_CONSENT_VERSION))
    elif not wanted:
        for row in active:
            row.withdrawn_at = func.now()


def _now(db: Session) -> datetime:
    return db.execute(select(func.now())).scalar_one()


def _retry_after(db: Session, user_id: uuid.UUID, now: datetime) -> int:
    """Seconds until another code may be sent to this account; 0 when one may be sent now."""
    times = db.scalars(
        select(EmailCode.created_at)
        .where(
            EmailCode.user_id == user_id, EmailCode.purpose == PURPOSE, EmailCode.created_at > now - timedelta(hours=1)
        )
        .order_by(EmailCode.created_at.desc())
    ).all()
    wait = 0.0
    if times and times[0] > now - COOLDOWN:
        wait = (times[0] + COOLDOWN - now).total_seconds()
    if len(times) >= MAX_CODES_PER_HOUR:
        wait = max(wait, (times[MAX_CODES_PER_HOUR - 1] + timedelta(hours=1) - now).total_seconds())
    return max(0, int(wait + 0.999))


def _new_code(db: Session, user_id: uuid.UUID, now: datetime) -> tuple[uuid.UUID, str]:
    code = f"{secrets.randbelow(1_000_000):06d}"
    row = EmailCode(id=uuid.uuid4(), user_id=user_id, purpose=PURPOSE, expires_at=now + CODE_TTL)
    row.code_hash = _hash_code(row.id, code)
    db.add(row)
    db.flush()
    return row.id, code


def _deliver(db: Session, code_id: uuid.UUID, message: email.Message) -> None:
    """Send after the transaction is committed. A code that couldn't be sent is removed, so it neither counts against
    the limits nor stays valid, and the caller is told plainly (DEGRADATION-01)."""
    result = email.send(message, idempotency_key=f"email-code-{code_id}")
    if result.status == "sent":
        return
    db.execute(delete(EmailCode).where(EmailCode.id == code_id))
    db.commit()
    raise Unavailable(
        "We couldn't send the email just now. Please try again in a minute.", code_reason="EMAIL_UNAVAILABLE"
    )


@router.post("/register", status_code=202, response_model=AcceptedOut, summary="Create an account; emails a code")
def register(body: RegisterIn, db: DB) -> AcceptedOut:
    address = body.email.lower()
    password_hash = _hasher.hash(body.password)  # slow on purpose: before taking a pooled connection (R08)
    settings = get_settings()
    cred = db.scalar(select(PasswordCredential).where(PasswordCredential.email == address).with_for_update())
    pending: tuple[uuid.UUID, str] | None = None
    now = _now(db)
    if cred is None:
        user = AppUser(
            issuer=settings.password_auth_issuer,
            subject=f"pwd|{uuid.uuid4().hex}",
            email=address,
            phone=body.phone,
            date_of_birth=body.date_of_birth,
            display_name=body.display_name,
        )
        db.add(user)
        db.flush()
        inserted = db.execute(
            insert(PasswordCredential)
            .values(user_id=user.id, email=address, password_hash=password_hash)
            .on_conflict_do_nothing(index_elements=["email"])
            .returning(PasswordCredential.user_id)
        ).scalar_one_or_none()
        if inserted is None:  # a concurrent registration of the same email won; same answer
            db.rollback()
            return AcceptedOut(detail=ACCEPTED)
        record(db, actor=user.id, action="account.register", target_type="app_user", target_id=str(user.id))
        if body.marketing_emails:
            db.add(ConsentRecord(user_id=user.id, document="marketing_messages", version=MARKETING_CONSENT_VERSION))
        pending = _new_code(db, user.id, now)
    elif cred.email_verified_at is None:
        cred.password_hash = password_hash
        owner = db.get(AppUser, cred.user_id)
        if owner is not None:
            owner.phone = body.phone
            owner.date_of_birth = body.date_of_birth
            _set_marketing(db, owner.id, body.marketing_emails)
            if body.display_name:
                owner.display_name = body.display_name
        if _retry_after(db, cred.user_id, now) == 0:
            pending = _new_code(db, cred.user_id, now)
    # An already verified address gets nothing new: the person signs in (or, later, resets the password).
    db.commit()
    if pending is not None:
        _deliver(db, pending[0], _code_message(address, pending[1]))
    return AcceptedOut(detail=ACCEPTED)


@router.post("/resend-code", status_code=202, response_model=AcceptedOut, summary="Email a new verification code")
def resend_code(body: EmailIn, db: DB) -> AcceptedOut:
    address = body.email.lower()
    cred = db.scalar(select(PasswordCredential).where(PasswordCredential.email == address).with_for_update())
    if cred is None or cred.email_verified_at is not None:
        db.rollback()
        return AcceptedOut(detail=ACCEPTED)
    now = _now(db)
    wait = _retry_after(db, cred.user_id, now)
    if wait:
        db.rollback()
        raise TooMany(f"Please wait {wait} seconds before asking for another code.", retry_after=wait)
    pending = _new_code(db, cred.user_id, now)
    db.commit()
    _deliver(db, pending[0], _code_message(address, pending[1]))
    return AcceptedOut(detail=ACCEPTED)


@router.post("/verify-email", response_model=TokenOut, summary="Confirm the email with its code and sign in")
def verify_email(body: VerifyIn, db: DB, response: Response) -> TokenOut:
    response.headers["Cache-Control"] = "no-store"
    wrong = InvalidCode("That code is wrong or has expired. Check the email or ask for a new code.")
    address = body.email.lower()
    cred = db.scalar(select(PasswordCredential).where(PasswordCredential.email == address).with_for_update())
    if cred is None or cred.email_verified_at is not None:
        db.rollback()
        raise wrong
    latest = db.scalar(
        select(EmailCode)
        .where(EmailCode.user_id == cred.user_id, EmailCode.purpose == PURPOSE)
        .order_by(EmailCode.created_at.desc())
        .limit(1)
    )
    now = _now(db)
    if latest is None or latest.consumed_at is not None or latest.expires_at <= now or latest.attempts >= MAX_TRIES:
        db.rollback()
        raise wrong
    if not hmac.compare_digest(_hash_code(latest.id, body.code.strip()), latest.code_hash):
        latest.attempts += 1
        db.commit()
        raise wrong
    latest.consumed_at = now
    cred.email_verified_at = now
    user = db.get(AppUser, cred.user_id)
    if user is None or user.status != "active":
        db.rollback()
        raise wrong
    record(db, actor=user.id, action="account.email_verified", target_type="app_user", target_id=str(user.id))
    subject, user_email = user.subject, user.email
    db.commit()
    issuer = get_local_issuer()
    return TokenOut(access_token=issuer.issue(subject, user_email), expires_in=issuer.ttl_s)


@router.post("/token", response_model=TokenOut, summary="Sign in with email and password")
def token(body: SignInIn, db: DB, response: Response) -> TokenOut:
    response.headers["Cache-Control"] = "no-store"
    cred = db.scalar(select(PasswordCredential).where(PasswordCredential.email == body.email.lower()))
    stored = cred.password_hash if cred else _DUMMY_HASH
    verified = cred is not None and cred.email_verified_at is not None
    user_id = cred.user_id if cred else None
    db.rollback()  # return the connection to the pool before the slow verify (R08)
    try:
        _hasher.verify(stored, body.password)
    except VerificationError as e:
        raise Unauthorized("Email or password is incorrect.") from e
    if user_id is None:
        raise Unauthorized("Email or password is incorrect.")
    user = db.get(AppUser, user_id)
    issuer = get_local_issuer()
    if user is None or user.status != "active" or user.issuer != issuer.issuer:
        raise Unauthorized("Email or password is incorrect.")
    if not verified:
        raise EmailNotVerified("Confirm your email first: enter the 6-digit code we sent, or ask for a new one.")
    return TokenOut(access_token=issuer.issue(user.subject, user.email), expires_in=issuer.ttl_s)
