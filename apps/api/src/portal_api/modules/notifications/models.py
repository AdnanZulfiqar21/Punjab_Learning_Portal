from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from portal_api.db import Base


class Notification(Base):
    """One event for one user: the in-app inbox row, rendered once. ``dedupe_key`` makes emitting idempotent, so
    retries and repeated jobs never notify twice."""

    __tablename__ = "notification"
    __table_args__ = (
        UniqueConstraint("user_id", "dedupe_key", name="uq_notification_dedupe"),
        CheckConstraint("category in ('service','reminder','promotional')", name="notification_category"),
        Index("ix_notification_user_created", "user_id", "created_at"),
        Index("ix_notification_unread", "user_id", postgresql_where=text("read_at is null")),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    event: Mapped[str] = mapped_column(String(40))
    category: Mapped[str] = mapped_column(String(12))
    dedupe_key: Mapped[str] = mapped_column(String(200))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(300))  # an app path, e.g. /practice/written/<id>
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationDelivery(Base):
    """One channel of one notification (email or push). Queued, then sent, failed (after bounded retries), skipped
    (nothing to deliver to, e.g. no registered device) or unavailable (no provider configured: BLOCKERS B04/B07)."""

    __tablename__ = "notification_delivery"
    __table_args__ = (
        UniqueConstraint("notification_id", "channel", name="uq_notification_delivery"),
        CheckConstraint("channel in ('email','push','sms')", name="notification_delivery_channel"),
        CheckConstraint(
            "status in ('queued','sent','failed','skipped','unavailable')", name="notification_delivery_status"
        ),
        Index("ix_notification_delivery_due", "next_attempt_at", postgresql_where=text("status = 'queued'")),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("notification.id", ondelete="RESTRICT"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    channel: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(12), default="queued")
    urgent: Mapped[bool] = mapped_column(Boolean, default=False)
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_error: Mapped[str | None] = mapped_column(Text)
    provider_ref: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationPreference(Base):
    """Per-user channels, categories, timezone and quiet hours (P15.S1.T3). Absent row = the defaults below."""

    __tablename__ = "notification_preference"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), primary_key=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    promotional_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    timezone: Mapped[str] = mapped_column(String(60), default="Asia/Karachi")
    quiet_start: Mapped[str] = mapped_column(String(5), default="22:00")  # local HH:MM; equal to end = no quiet hours
    quiet_end: Mapped[str] = mapped_column(String(5), default="07:00")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NotificationSuppression(Base):
    """A destination that must not be sent to (P15.S4.T1): a bounced or complained address, or a user's request.
    Stored as a SHA-256 of the normalised destination, never the address itself."""

    __tablename__ = "notification_suppression"
    __table_args__ = (
        UniqueConstraint("channel", "destination_hash", name="uq_notification_suppression"),
        CheckConstraint("channel in ('email','push','sms')", name="notification_suppression_channel"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel: Mapped[str] = mapped_column(String(8))
    destination_hash: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PushToken(Base):
    """A device's push address (Expo push token). Registered by the native app; one row per token."""

    __tablename__ = "push_token"
    __table_args__ = (CheckConstraint("platform in ('ios','android')", name="push_token_platform"),)
    token: Mapped[str] = mapped_column(String(200), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    platform: Mapped[str] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    failures: Mapped[int] = mapped_column(Integer, default=0)
