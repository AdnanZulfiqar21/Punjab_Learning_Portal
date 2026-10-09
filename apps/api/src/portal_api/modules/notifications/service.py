"""Emitting notifications, the inbox and preferences (P15.S1.T1/T3).

``notify`` is called inside the caller's transaction, so a notification exists exactly when the event it reports was
committed. It is idempotent per (user, dedupe key). Email/push deliveries are queued for the worker in ``delivery``;
the in-app inbox needs no delivery. Times shown in texts use the learner's timezone (Asia/Karachi by default);
everything is stored in UTC.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from portal_api.errors import NotFound, Unprocessable
from portal_api.modules.notifications.models import (
    Notification,
    NotificationDelivery,
    NotificationPreference,
    NotificationSuppression,
    PushToken,
)
from portal_api.modules.notifications.templates import render

DEFAULTS = NotificationPreference(
    email_enabled=True,
    push_enabled=True,
    reminders_enabled=True,
    promotional_opt_in=False,
    timezone="Asia/Karachi",
    quiet_start="22:00",
    quiet_end="07:00",
)
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def preferences(db: Session, user_id: uuid.UUID) -> NotificationPreference:
    return db.get(NotificationPreference, user_id) or DEFAULTS


def local_time(db: Session, user_id: uuid.UUID, at: datetime) -> str:
    """A timestamp as the learner reads it: their timezone, unambiguous date and time."""
    tz = ZoneInfo(preferences(db, user_id).timezone)
    return at.astimezone(tz).strftime("%d %b %Y, %H:%M")


def notify(
    db: Session,
    user_id: uuid.UUID,
    event: str,
    params: dict[str, Any],
    *,
    dedupe_key: str,
    link: str | None = None,
) -> Notification | None:
    """Record one notification (and queue its email/push deliveries) in the caller's transaction. Returns None when
    it already exists for this key or the user opted out of the category. Never commits."""
    t, title, body = render(event, {k: str(v) for k, v in params.items()})
    prefs = preferences(db, user_id)
    if t.category == "promotional" and not prefs.promotional_opt_in:
        return None
    if t.category == "reminder" and not prefs.reminders_enabled:
        return None
    row = db.execute(
        insert(Notification)
        .values(
            id=uuid.uuid4(),
            user_id=user_id,
            event=event,
            category=t.category,
            dedupe_key=dedupe_key[:200],
            params={k: str(v)[:300] for k, v in params.items()},
            title=title,
            body=body,
            link=link,
        )
        .on_conflict_do_nothing(constraint="uq_notification_dedupe")
        .returning(Notification.id)
    ).first()
    if row is None:
        return None
    for channel in t.channels:
        if (channel == "email" and prefs.email_enabled) or (channel == "push" and prefs.push_enabled):
            db.add(NotificationDelivery(notification_id=row[0], user_id=user_id, channel=channel, urgent=t.urgent))
    db.flush()
    return db.get(Notification, row[0])


# ------------------------------------------------------------------ inbox
def inbox(db: Session, user_id: uuid.UUID, offset: int, limit: int) -> tuple[list[Notification], int]:
    rows = list(
        db.scalars(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc(), Notification.id)
            .offset(offset)
            .limit(limit)
        )
    )
    unread = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
    )
    return rows, int(unread or 0)


def mark_read(db: Session, user_id: uuid.UUID, notification_id: uuid.UUID | None) -> None:
    stmt = update(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None))
    if notification_id is not None:
        if (
            db.scalar(
                select(Notification.id).where(Notification.id == notification_id, Notification.user_id == user_id)
            )
            is None
        ):
            raise NotFound("Notification not found.")
        stmt = stmt.where(Notification.id == notification_id)
    db.execute(stmt.values(read_at=func.now()))
    db.commit()


# ------------------------------------------------------------------ preferences
def save_preferences(db: Session, user_id: uuid.UUID, values: dict[str, Any]) -> NotificationPreference:
    try:
        ZoneInfo(str(values["timezone"]))
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        raise Unprocessable("Choose a valid timezone, for example Asia/Karachi.") from None
    for k in ("quiet_start", "quiet_end"):
        if not HHMM.match(str(values[k])):
            raise Unprocessable("Quiet hours use 24-hour HH:MM times.")
    db.execute(
        insert(NotificationPreference)
        .values(user_id=user_id, **values)
        .on_conflict_do_update(index_elements=["user_id"], set_={**values, "updated_at": func.now()})
    )
    db.commit()
    pref = db.get(NotificationPreference, user_id, populate_existing=True)
    assert pref is not None
    return pref


def quiet_until(prefs: NotificationPreference, now: datetime) -> datetime | None:
    """If ``now`` falls inside the learner's quiet hours, the UTC time they end; otherwise None."""
    if prefs.quiet_start == prefs.quiet_end:
        return None
    tz = ZoneInfo(prefs.timezone)
    local = now.astimezone(tz)
    start = time.fromisoformat(prefs.quiet_start)
    end = time.fromisoformat(prefs.quiet_end)
    t = local.time()
    inside = (start <= t or t < end) if start > end else (start <= t < end)
    if not inside:
        return None
    end_day = local.date() if t < end else local.date() + timedelta(days=1)
    return datetime.combine(end_day, end, tzinfo=tz).astimezone(UTC)


# ------------------------------------------------------------------ push tokens
def register_push_token(db: Session, user_id: uuid.UUID, token: str, platform: str) -> None:
    if not (token.startswith("ExponentPushToken[") or token.startswith("ExpoPushToken[")) or len(token) > 200:
        raise Unprocessable("That isn't a device push token from this app.")
    db.execute(
        insert(PushToken)
        .values(token=token, user_id=user_id, platform=platform)
        .on_conflict_do_update(
            index_elements=["token"],
            set_={"user_id": user_id, "platform": platform, "last_seen_at": func.now(), "failures": 0},
        )
    )
    db.commit()


def remove_push_token(db: Session, user_id: uuid.UUID, token: str) -> None:
    row = db.get(PushToken, token)
    if row is not None and row.user_id == user_id:
        db.delete(row)
        db.commit()


# ------------------------------------------------------------------ operations (P15.S4.T1)
def destination_hash(destination: str) -> str:
    import hashlib

    return hashlib.sha256(destination.strip().lower().encode()).hexdigest()


def is_suppressed(db: Session, channel: str, destination: str) -> bool:
    return (
        db.scalar(
            select(NotificationSuppression.id).where(
                NotificationSuppression.channel == channel,
                NotificationSuppression.destination_hash == destination_hash(destination),
            )
        )
        is not None
    )


def suppress(db: Session, actor: uuid.UUID, channel: str, destination: str, reason: str) -> None:
    from portal_api.modules.audit.models import record

    db.execute(
        insert(NotificationSuppression)
        .values(channel=channel, destination_hash=destination_hash(destination), reason=reason[:500], created_by=actor)
        .on_conflict_do_nothing(constraint="uq_notification_suppression")
    )
    record(
        db,
        actor=actor,
        action="notification.suppressed",
        target_type="notification_suppression",
        target_id=destination_hash(destination)[:16],
        details={"channel": channel, "reason": reason[:200]},
    )
    db.commit()


def unsuppress(db: Session, actor: uuid.UUID, channel: str, destination: str) -> None:
    from portal_api.modules.audit.models import record

    row = db.scalar(
        select(NotificationSuppression).where(
            NotificationSuppression.channel == channel,
            NotificationSuppression.destination_hash == destination_hash(destination),
        )
    )
    if row is None:
        raise NotFound("That destination isn't suppressed.")
    db.delete(row)
    record(
        db,
        actor=actor,
        action="notification.unsuppressed",
        target_type="notification_suppression",
        target_id=destination_hash(destination)[:16],
        details={"channel": channel},
    )
    db.commit()


def dead_letters(db: Session, limit: int) -> list[tuple[NotificationDelivery, Notification]]:
    """Deliveries that stopped as failed (after their retries), newest first, for inspection and requeueing."""
    rows = db.execute(
        select(NotificationDelivery, Notification)
        .join(Notification, Notification.id == NotificationDelivery.notification_id)
        .where(NotificationDelivery.status == "failed")
        .order_by(NotificationDelivery.created_at.desc())
        .limit(limit)
    ).all()
    return [(d, n) for d, n in rows]


def requeue(db: Session, actor: uuid.UUID, delivery_id: uuid.UUID) -> NotificationDelivery:
    from portal_api.errors import Conflict
    from portal_api.modules.audit.models import record

    d = db.scalar(select(NotificationDelivery).where(NotificationDelivery.id == delivery_id).with_for_update())
    if d is None:
        raise NotFound("Delivery not found.")
    if d.status != "failed":
        raise Conflict("Only a failed delivery can be retried.")
    d.status, d.attempts, d.last_error = "queued", 0, None
    d.next_attempt_at = func.now()
    record(
        db,
        actor=actor,
        action="notification.requeued",
        target_type="notification_delivery",
        target_id=str(d.id),
        details={"channel": d.channel},
    )
    db.commit()
    db.refresh(d)
    return d


def metrics(db: Session, days: int) -> dict[str, Any]:
    """Delivery outcomes per channel, measured separately from whether people read the in-app notice (P15.S4.T1)."""
    from sqlalchemy import text as sql

    since = {"d": days}
    delivered = db.execute(
        sql(
            "select channel, status, count(*) from notification_delivery "
            "where created_at > now() - make_interval(days => :d) group by 1, 2"
        ),
        since,
    ).all()
    read = db.execute(
        sql(
            "select event, count(*), count(read_at) from notification "
            "where created_at > now() - make_interval(days => :d) group by 1 order by 1"
        ),
        since,
    ).all()
    by_channel: dict[str, dict[str, int]] = {}
    for channel, status, n in delivered:
        by_channel.setdefault(channel, {})[status] = int(n)
    return {
        "days": days,
        "deliveries": by_channel,
        "inbox": {event: {"created": int(c), "read": int(r)} for event, c, r in read},
    }
