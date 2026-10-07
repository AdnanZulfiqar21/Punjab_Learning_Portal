"""Trial, entitlements and the written-assessment allowance ledger (roadmap §16, P14.S1/S5, §20.13.4, W08.S1).

* `trial_grant`: at most one per account per program (`PLATFORM_TRIAL_30D` is a constant identity; terms revisions
  never reset consumption). Starts at the grant's commit time and ends exactly 30 x 24 h later.
* `entitlement`: every access source with provenance (trial, paid, scholarship, promotional, pilot). Access is resolved
  from valid sources; nothing is ever deleted (revocation/refund are recorded states).
* `allowance_event`: an append-only ledger of written-assessment units per bucket: RESERVED at start, ACCEPTED at
  seal (selected questions), CONSUMED once at first released marks, RELEASED for unused/unanswered/expired work,
  REMEDY_CREDIT for authorised remedies. Idempotent per (attempt, kind).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from portal_api.db import Base

TRIAL_PROGRAM = "PLATFORM_TRIAL_30D"
OFFER_TERMS_VERSION = 1


class TrialGrant(Base):
    __tablename__ = "trial_grant"
    __table_args__ = (UniqueConstraint("user_id", "program", name="uq_trial_grant_program"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    program: Mapped[str] = mapped_column(String(40), default=TRIAL_PROGRAM)
    offer_terms_version: Mapped[int] = mapped_column(SmallInteger, default=OFFER_TERMS_VERSION)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(12), default="active")  # active | converted | revoked
    client: Mapped[str] = mapped_column(String(10))  # web | native, recorded for the device decision (P14.S6)
    entitlement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("entitlement.id", ondelete="RESTRICT"))


class Entitlement(Base):
    __tablename__ = "entitlement"
    __table_args__ = (
        CheckConstraint("source in ('trial','paid','scholarship','promotional','pilot')", name="entitlement_source"),
        CheckConstraint("status in ('active','revoked','refunded')", name="entitlement_status"),
        CheckConstraint("ends_at > starts_at", name="entitlement_period"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    source: Mapped[str] = mapped_column(String(12))
    product_code: Mapped[str] = mapped_column(String(40), default="platform")
    scope: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # {} = the whole active academic scope
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(10), default="active")
    written_units: Mapped[int] = mapped_column(Integer, default=0)  # disclosed finite written allowance for the period
    reason: Mapped[str] = mapped_column(Text)
    granted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(Text)


class AllowanceEvent(Base):
    __tablename__ = "allowance_event"
    __table_args__ = (
        UniqueConstraint("attempt_id", "kind", name="uq_allowance_attempt_kind"),
        CheckConstraint(
            "kind in ('RESERVED','ACCEPTED','CONSUMED','RELEASED','REMEDY_CREDIT')", name="allowance_event_kind"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    entitlement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entitlement.id", ondelete="RESTRICT"), index=True)
    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)  # written attempt
    kind: Mapped[str] = mapped_column(String(14))
    units: Mapped[int] = mapped_column(Integer)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
