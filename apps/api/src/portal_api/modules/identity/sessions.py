"""Application sessions (P04.S1.T2/T3, roadmap §5.3).

A client authenticates with the identity provider once and exchanges that verified access token for an opaque,
revocable application session token. The web server keeps it in an HTTP-only cookie (browser JavaScript never sees a
token); native apps keep it in OS secure storage. Only the SHA-256 of a session token is stored, and tokens are never
logged. Students can list and revoke their sessions; a revoked, expired or idle session stops working immediately.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base

PREFIX = "pls_"  # distinguishes application session tokens from identity-provider JWTs
SessionKind = Literal["web", "native"]
# Proposed defaults (configurable later via policy, roadmap §16.9 / P04.S1.T3).
ABSOLUTE_LIFETIME = {"web": timedelta(days=30), "native": timedelta(days=60)}
IDLE_TIMEOUT = {"web": timedelta(days=7), "native": timedelta(days=30)}
LAST_SEEN_RESOLUTION = timedelta(seconds=60)
# STAFF-MFA-01: how long a session's own second-factor check counts before the code is asked for again.
MFA_STEP_UP_WINDOW = timedelta(hours=12)


class UserSession(Base):
    __tablename__ = "user_session"
    __table_args__ = (
        CheckConstraint("kind in ('web','native')", name="user_session_kind"),
        Index("ix_user_session_user_active", "user_id", postgresql_where="revoked_at is null"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    kind: Mapped[str] = mapped_column(String(10))
    device_label: Mapped[str | None] = mapped_column(String(120))
    user_agent: Mapped[str | None] = mapped_column(Text)
    mfa: Mapped[bool] = mapped_column(Boolean, default=False)
    # STAFF-MFA-01: when this session proved the second factor itself (an authenticator code). Empty when the
    # identity provider asserted it at sign-in.
    mfa_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(String(40))


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create(
    db: Session,
    *,
    user_id: uuid.UUID,
    kind: SessionKind,
    mfa: bool,
    device_label: str | None,
    user_agent: str | None,
) -> tuple[UserSession, str]:
    token = PREFIX + secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    row = UserSession(
        user_id=user_id,
        token_hash=_hash(token),
        kind=kind,
        mfa=mfa,
        device_label=(device_label or None),
        user_agent=(user_agent or "")[:400] or None,
        created_at=now,
        last_seen_at=now,
        expires_at=now + ABSOLUTE_LIFETIME[kind],
    )
    db.add(row)
    db.flush()
    return row, token


def resolve(db: Session, token: str) -> UserSession | None:
    """Return the live session for a presented token (or None), refreshing last_seen at a coarse resolution."""
    row = db.scalar(select(UserSession).where(UserSession.token_hash == _hash(token)))
    if row is None or row.revoked_at is not None:
        return None
    now = datetime.now(UTC)
    if now >= row.expires_at:
        return None
    if now - row.last_seen_at >= IDLE_TIMEOUT[row.kind]:
        row.revoked_at, row.revoke_reason = now, "idle_timeout"
        db.commit()
        return None
    if now - row.last_seen_at >= LAST_SEEN_RESOLUTION:
        row.last_seen_at = now
        db.commit()
    return row


def has_mfa(row: UserSession, now: datetime | None = None) -> bool:
    """Whether this session counts as multi-factor now: asserted by the identity provider at sign-in, or proved here
    with an authenticator code within the step-up window (STAFF-MFA-01)."""
    if not row.mfa:
        return False
    if row.mfa_verified_at is None:
        return True
    return (now or datetime.now(UTC)) - row.mfa_verified_at < MFA_STEP_UP_WINDOW


def revoke(db: Session, row: UserSession, reason: str) -> None:
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        row.revoke_reason = reason
