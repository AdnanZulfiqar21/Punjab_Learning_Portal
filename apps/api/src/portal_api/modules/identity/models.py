"""Identity domain (P04, roadmap §5.2 Identity). Authentication is delegated to an OIDC issuer; the application owns
the user record, profile, roles and consent. A user is identified by (issuer, subject), never by email alone."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from portal_api.db import Base


class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = (
        UniqueConstraint("issuer", "subject"),
        CheckConstraint("status in ('active','suspended','deleted')", name="app_user_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    issuer: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    display_name: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(12), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped[StudentProfile | None] = relationship(back_populates="user", uselist=False)
    role_grants: Mapped[list[StaffRoleGrant]] = relationship(
        back_populates="user", foreign_keys="StaffRoleGrant.user_id", order_by="StaffRoleGrant.granted_at"
    )


class StudentProfile(Base):
    """Onboarding/learning preferences (P04.S3.T1). Deliberately no CNIC or other identity documents."""

    __tablename__ = "student_profile"
    __table_args__ = (
        CheckConstraint("grade is null or grade in (11, 12)", name="student_profile_grade"),
        CheckConstraint("daily_minutes is null or daily_minutes between 10 and 600", name="student_profile_minutes"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True)
    grade: Mapped[int | None] = mapped_column(SmallInteger)
    stream: Mapped[str | None] = mapped_column(String(30))
    subjects: Mapped[list[str]] = mapped_column(JSONB, default=list)
    target_exams: Mapped[list[str]] = mapped_column(JSONB, default=list)
    target_year: Mapped[int | None] = mapped_column(SmallInteger)
    explanation_language: Mapped[str] = mapped_column(String(12), default="en")
    daily_minutes: Mapped[int | None] = mapped_column(SmallInteger)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[AppUser] = relationship(back_populates="profile")


class StaffRoleGrant(Base):
    """A role held by a person, optionally scoped (e.g. subject reviewer for Class XI Chemistry). Never deleted:
    revocation is recorded, so the history of who could do what stays auditable (P04.S2.T2)."""

    __tablename__ = "staff_role_grant"
    __table_args__ = (Index("ix_staff_role_grant_active", "user_id", "role", postgresql_where="revoked_at is null"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    role: Mapped[str] = mapped_column(String(40))
    scope: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    granted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reason: Mapped[str] = mapped_column(Text)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    revoke_reason: Mapped[str | None] = mapped_column(Text)

    user: Mapped[AppUser] = relationship(back_populates="role_grants", foreign_keys=[user_id])


class ConsentRecord(Base):
    """Versioned acceptance of terms/privacy and optional choices (P04.S4.T2). Withdrawal is recorded, not deleted."""

    __tablename__ = "consent_record"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), index=True)
    document: Mapped[str] = mapped_column(String(40))  # terms | privacy | marketing_messages | …
    version: Mapped[str] = mapped_column(String(40))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DevCredential(Base):
    """Email/password credentials for the development-only local issuer. Never used in staging/production (the
    startup validator refuses dev_auth there); production authentication lives in the managed OIDC provider."""

    __tablename__ = "dev_credential"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
