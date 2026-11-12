"""Two-step sign-in with an authenticator app (STAFF-MFA-01, security audit 2026-11; owner 2026-11-13).

Sensitive staff permissions need a session that proved a second factor (`permissions.MFA_REQUIRED`). The portal's own
password sign-in had no way to give one outside development. This adds it: a time-based one-time code (TOTP, RFC 6238:
SHA-1, 6 digits, 30 seconds), the kind every authenticator app shows.

How it works:
* **Set up** (`enrol`, then `confirm` with the first code): the secret is created on the server, shown once, and kept
  encrypted with the deployment's `mfa_secret_key`. Confirming returns eight one-time recovery codes, shown once and
  stored only as hashes.
* **Step up** (`verify`): a signed-in session enters the current code and becomes a multi-factor session for twelve
  hours. Nothing changes at sign-in itself, so learners never see it; staff are asked when an action needs it.
* A code works once (the time step is remembered). Five wrong codes lock checking for fifteen minutes.
* A recovery code works in place of a code, once. Turning two-step sign-in off needs a code too.
* A lost phone with no recovery codes left: an operator runs `portal-mfa-reset` (audited), and the person sets it up
  again.
* A password reset signs every session out, so the new session starts without a second factor.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import secrets
import struct
import sys
import uuid
from datetime import datetime, timedelta
from typing import Annotated
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import BigInteger, DateTime, ForeignKey, SmallInteger, String, Text, delete, func, select, text, update
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.budget import process_class
from portal_api.config import get_settings
from portal_api.db import Base, get_session, get_sessionmaker
from portal_api.errors import AppError, Conflict, TooMany
from portal_api.modules.audit.models import record
from portal_api.modules.identity.deps import CurrentPrincipal, Principal, require_recent_sign_in
from portal_api.modules.identity.models import AppUser
from portal_api.modules.identity.sessions import UserSession

router = APIRouter(prefix="/v1/me/mfa", tags=["mfa"])
DB = Annotated[Session, Depends(get_session)]

ISSUER_NAME = "Sirf Concepts"
PERIOD_S = 30
DRIFT_STEPS = 1  # the code before and after the current one is accepted (a phone clock a little off)
MAX_WRONG = 5
LOCK = timedelta(minutes=15)
RECOVERY_CODES = 8
_RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no look-alikes (0/o, 1/l/i)


class TotpCredential(Base):
    """One person's authenticator secret. `confirmed_at` is empty until the first code proved the app was set up."""

    __tablename__ = "totp_credential"
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    secret_enc: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_step: Mapped[int | None] = mapped_column(BigInteger)  # the newest time step already used: no replay
    failed_attempts: Mapped[int] = mapped_column(SmallInteger, default=0, server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TotpRecoveryCode(Base):
    """A one-time recovery code. Only a salted SHA-256 is stored."""

    __tablename__ = "totp_recovery_code"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InvalidCode(AppError):
    status = 400
    code = "INVALID_CODE"


WRONG = "That code isn't right. Enter the 6-digit code your authenticator app shows now."


# ------------------------------------------------------------------ the algorithm and the stored secret
def _fernet() -> Fernet:
    key = hashlib.sha256(get_settings().mfa_secret_key.get_secret_value().encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def _seal(secret: bytes) -> str:
    return _fernet().encrypt(secret).decode()


def _open(cred: TotpCredential) -> bytes:
    try:
        return _fernet().decrypt(cred.secret_enc.encode())
    except InvalidToken as e:  # the deployment key changed: the secret can't be read; the person sets up again
        raise Conflict(
            "Two-step sign-in needs to be set up again. Ask an administrator to reset it.", code_reason="MFA_RESET"
        ) from e


def totp(secret: bytes, step: int) -> str:
    mac = hmac.new(secret, struct.pack(">Q", step), "sha1").digest()
    at = mac[-1] & 0x0F
    return f"{(struct.unpack('>I', mac[at : at + 4])[0] & 0x7FFFFFFF) % 1_000_000:06d}"


def _step(now: datetime) -> int:
    return int(now.timestamp()) // PERIOD_S


def _recovery_hash(user_id: uuid.UUID, code: str) -> str:
    return hashlib.sha256(f"{user_id}:{code}".encode()).hexdigest()


def _clean(code: str) -> str:
    return "".join(code.split()).replace("-", "").lower()


def _now(db: Session) -> datetime:
    return db.execute(select(func.now())).scalar_one()


def _check(db: Session, cred: TotpCredential, code: str, now: datetime, *, recovery: bool = True) -> str:
    """Accept the current code (or, when allowed, an unused recovery code) and say which: "totp" or "recovery". A wrong
    code is counted and committed, then refused; five in a row lock checking for a while."""
    if cred.locked_until is not None and cred.locked_until > now:
        wait = max(1, int((cred.locked_until - now).total_seconds()))
        db.rollback()
        raise TooMany("Too many wrong codes. Please wait a few minutes and try again.", retry_after=wait)
    entered = _clean(code)
    method: str | None = None
    if len(entered) == 6 and entered.isdigit():
        secret, current = _open(cred), _step(now)
        for step in range(current - DRIFT_STEPS, current + DRIFT_STEPS + 1):
            if hmac.compare_digest(totp(secret, step), entered) and step > (cred.last_step or 0):
                cred.last_step, method = step, "totp"
                break
    elif recovery and len(entered) == 10:
        row = db.scalar(
            select(TotpRecoveryCode)
            .where(
                TotpRecoveryCode.user_id == cred.user_id,
                TotpRecoveryCode.code_hash == _recovery_hash(cred.user_id, entered),
                TotpRecoveryCode.used_at.is_(None),
            )
            .with_for_update()
        )
        if row is not None:
            row.used_at, method = now, "recovery"
    if method is None:
        cred.failed_attempts += 1
        if cred.failed_attempts >= MAX_WRONG:
            cred.failed_attempts, cred.locked_until = 0, now + LOCK
        db.commit()
        raise InvalidCode(WRONG)
    cred.failed_attempts, cred.locked_until = 0, None
    return method


def _locked(db: Session, user_id: uuid.UUID) -> TotpCredential | None:
    return db.scalar(select(TotpCredential).where(TotpCredential.user_id == user_id).with_for_update())


def _mark(session: UserSession | None, now: datetime) -> None:
    if session is not None:
        session.mfa, session.mfa_verified_at = True, now


def _new_recovery_codes(db: Session, user_id: uuid.UUID) -> list[str]:
    db.execute(delete(TotpRecoveryCode).where(TotpRecoveryCode.user_id == user_id))
    codes = ["".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(10)) for _ in range(RECOVERY_CODES)]
    for c in codes:
        db.add(TotpRecoveryCode(user_id=user_id, code_hash=_recovery_hash(user_id, c)))
    return [f"{c[:5]}-{c[5:]}" for c in codes]


def remove(db: Session, user_id: uuid.UUID) -> bool:
    """Forget the person's authenticator and recovery codes, and end the second factor on their sessions."""
    had = db.scalar(select(func.count()).select_from(TotpCredential).where(TotpCredential.user_id == user_id))
    db.execute(delete(TotpCredential).where(TotpCredential.user_id == user_id))
    db.execute(delete(TotpRecoveryCode).where(TotpRecoveryCode.user_id == user_id))
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.mfa_verified_at.is_not(None))
        .values(mfa=False, mfa_verified_at=None)
    )
    return bool(had)


# ------------------------------------------------------------------ API
class MfaCodeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=6, max_length=20, description="The 6-digit code, or a recovery code")


class MfaStatusOut(BaseModel):
    enabled: bool
    session_verified: bool = Field(description="This session has proved the second factor and it is still fresh")
    recovery_codes_left: int


class MfaEnrolOut(BaseModel):
    secret: str = Field(description="The setup key to type into the authenticator app (shown once)")
    otpauth_uri: str = Field(description="The same as a link or QR content for the authenticator app")


class MfaRecoveryOut(BaseModel):
    recovery_codes: list[str] = Field(description="One-time codes for a lost phone. Shown once: keep them safe")


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def _status(db: Session, who: Principal) -> MfaStatusOut:
    cred = db.get(TotpCredential, who.user.id)
    enabled = cred is not None and cred.confirmed_at is not None
    left = db.scalar(
        select(func.count())
        .select_from(TotpRecoveryCode)
        .where(TotpRecoveryCode.user_id == who.user.id, TotpRecoveryCode.used_at.is_(None))
    )
    return MfaStatusOut(enabled=enabled, session_verified=who.claims.mfa, recovery_codes_left=int(left or 0))


@router.get("", response_model=MfaStatusOut, summary="Whether two-step sign-in is set up, and this session's state")
def status(db: DB, who: CurrentPrincipal, response: Response) -> MfaStatusOut:
    _private(response)
    return _status(db, who)


@router.post("/enrol", response_model=MfaEnrolOut, summary="Start setting up an authenticator app (shows the key once)")
def enrol(db: DB, who: CurrentPrincipal, response: Response) -> MfaEnrolOut:
    _private(response)
    require_recent_sign_in(who)
    cred = _locked(db, who.user.id)
    if cred is not None and cred.confirmed_at is not None:
        db.rollback()
        raise Conflict("Two-step sign-in is already set up. Turn it off first to set it up again.")
    secret = secrets.token_bytes(20)
    if cred is None:
        db.add(TotpCredential(user_id=who.user.id, secret_enc=_seal(secret)))
    else:  # an unfinished set-up starts again with a new key
        cred.secret_enc, cred.last_step, cred.failed_attempts, cred.locked_until = _seal(secret), None, 0, None
    db.commit()
    key = base64.b32encode(secret).decode().rstrip("=")
    label = quote(f"{ISSUER_NAME}:{who.user.email or who.user.id}")
    uri = f"otpauth://totp/{label}?secret={key}&issuer={quote(ISSUER_NAME)}&algorithm=SHA1&digits=6&period={PERIOD_S}"
    return MfaEnrolOut(secret=" ".join(key[i : i + 4] for i in range(0, len(key), 4)), otpauth_uri=uri)


@router.post("/confirm", response_model=MfaRecoveryOut, summary="Finish set-up with the first code")
def confirm(body: MfaCodeIn, db: DB, who: CurrentPrincipal, response: Response) -> MfaRecoveryOut:
    _private(response)
    cred = _locked(db, who.user.id)
    if cred is None:
        db.rollback()
        raise Conflict("Start the set-up first.", code_reason="MFA_NOT_SET_UP")
    if cred.confirmed_at is not None:
        db.rollback()
        raise Conflict("Two-step sign-in is already set up.")
    now = _now(db)
    _check(db, cred, body.code, now, recovery=False)
    cred.confirmed_at = now
    codes = _new_recovery_codes(db, who.user.id)
    _mark(who.session, now)
    record(db, actor=who.user.id, action="mfa.enabled", target_type="app_user", target_id=str(who.user.id))
    db.commit()
    return MfaRecoveryOut(recovery_codes=codes)


@router.post("/verify", response_model=MfaStatusOut, summary="Prove the second factor for this session (12 hours)")
def verify(body: MfaCodeIn, db: DB, who: CurrentPrincipal, response: Response) -> MfaStatusOut:
    _private(response)
    if who.session is None:
        raise Conflict("Sign in on this device first.", code_reason="SESSION_REQUIRED")
    cred = _locked(db, who.user.id)
    if cred is None or cred.confirmed_at is None:
        db.rollback()
        raise Conflict("Two-step sign-in isn't set up on this account yet.", code_reason="MFA_NOT_SET_UP")
    now = _now(db)
    method = _check(db, cred, body.code, now)
    _mark(who.session, now)
    record(
        db,
        actor=who.user.id,
        action="mfa.verified",
        target_type="user_session",
        target_id=str(who.session.id),
        details={"method": method},
    )
    db.commit()
    out = _status(db, who)
    return out.model_copy(update={"session_verified": True})


@router.post("/disable", status_code=204, summary="Turn two-step sign-in off (needs a code)")
def disable(body: MfaCodeIn, db: DB, who: CurrentPrincipal) -> Response:
    cred = _locked(db, who.user.id)
    if cred is None or cred.confirmed_at is None:
        db.rollback()
        raise Conflict("Two-step sign-in isn't set up on this account.", code_reason="MFA_NOT_SET_UP")
    method = _check(db, cred, body.code, _now(db))
    db.flush()
    remove(db, who.user.id)
    record(
        db,
        actor=who.user.id,
        action="mfa.disabled",
        target_type="app_user",
        target_id=str(who.user.id),
        details={"method": method},
    )
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


# ------------------------------------------------------------------ operator command (a lost phone)
@process_class("reserve")
def main(argv: list[str] | None = None) -> int:
    """portal-mfa-reset --email person@example.org --reason "lost phone, identity checked by the owner"

    Removes the person's authenticator and recovery codes so they can set two-step sign-in up again. Audited with
    actor=None and via=cli."""
    ap = argparse.ArgumentParser(description=main.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--email", required=True)
    ap.add_argument("--reason", required=True)
    args = ap.parse_args(argv)
    with get_sessionmaker()() as db:
        users = db.scalars(select(AppUser).where(func.lower(AppUser.email) == args.email.lower())).all()
        if len(users) != 1:
            print(f"expected exactly one account with email {args.email}, found {len(users)}", file=sys.stderr)
            return 1
        had = remove(db, users[0].id)
        record(
            db,
            actor=None,
            action="mfa.reset",
            target_type="app_user",
            target_id=str(users[0].id),
            details={"reason": args.reason, "via": "cli", "was_set_up": had},
        )
        db.commit()
        print(f"two-step sign-in reset for {users[0].id} (was set up: {had})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
