"""Queued email/push delivery (P15.S1.T2).

The worker (``portal-notification-worker``) claims due deliveries with SKIP LOCKED, so several workers never send the
same one. Non-urgent deliveries wait out the learner's quiet hours and an hourly cap per user and channel, so a burst
of events (or a retry storm) never floods anyone. Failures retry with backoff, then stop as ``failed``. A channel with
no configured provider records ``unavailable`` with the reason instead of pretending to send:

* email: ``dev_outbox`` (development/test only; records the rendered message, refused in staging/production) or
  ``none`` until an approved sender exists (BLOCKERS B04);
* push: ``none`` until installable builds and push credentials exist (BLOCKERS B07). Tokens can be registered now.

SMS is an optional approved-cost channel (roadmap) and has no adapter.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from portal_api.config import get_settings
from portal_api.db import get_sessionmaker
from portal_api.modules.identity.models import AppUser
from portal_api.modules.notifications import service
from portal_api.modules.notifications.models import Notification, NotificationDelivery, PushToken

log = logging.getLogger("portal.notifications")
MAX_ATTEMPTS = 5
HOURLY_CAP = 10  # non-urgent messages per user, channel and hour


@dataclass(frozen=True)
class Outcome:
    status: str  # sent | failed | skipped | unavailable
    ref: str | None = None
    error: str | None = None


def _send_email(db: Session, d: NotificationDelivery, n: Notification) -> Outcome:
    adapter = get_settings().notification_email_adapter
    if adapter == "none":
        return Outcome("unavailable", error="no email sender is configured (BLOCKERS B04)")
    user = db.get(AppUser, d.user_id)
    if user is None or not user.email:
        return Outcome("skipped", error="no email address on the account")
    # dev_outbox: development/test only (refused in staging/production by the configuration validator).
    log.info("dev email to=%s subject=%r", user.email, n.title)
    return Outcome("sent", ref=f"dev-outbox:{n.id}")


def _send_push(db: Session, d: NotificationDelivery, n: Notification) -> Outcome:
    tokens = db.scalar(select(func.count()).select_from(PushToken).where(PushToken.user_id == d.user_id))
    if not tokens:
        return Outcome("skipped", error="no registered device")
    return Outcome("unavailable", error="no push provider is configured (BLOCKERS B07)")


ADAPTERS = {"email": _send_email, "push": _send_push}


def _now(db: Session) -> datetime:
    now: datetime = db.execute(select(func.clock_timestamp())).scalar_one()
    return now


def deliver_due(db: Session, limit: int = 100) -> int:
    """Process up to ``limit`` due deliveries, one short transaction each. Returns how many reached a final state."""
    now = _now(db)
    ids = list(
        db.scalars(
            select(NotificationDelivery.id)
            .where(NotificationDelivery.status == "queued", NotificationDelivery.next_attempt_at <= now)
            .order_by(NotificationDelivery.next_attempt_at)
            .limit(limit)
        )
    )
    db.rollback()
    done = 0
    for delivery_id in ids:
        d = db.scalar(
            select(NotificationDelivery)
            .where(NotificationDelivery.id == delivery_id, NotificationDelivery.status == "queued")
            .with_for_update(skip_locked=True)
        )
        if d is None:  # another worker has it, or it's no longer queued
            db.rollback()
            continue
        now = _now(db)
        if not d.urgent:
            later = service.quiet_until(service.preferences(db, d.user_id), now)
            if later is not None:
                d.next_attempt_at = later
                db.commit()
                continue
            recent = db.scalar(
                select(func.count())
                .select_from(NotificationDelivery)
                .where(
                    NotificationDelivery.user_id == d.user_id,
                    NotificationDelivery.channel == d.channel,
                    NotificationDelivery.status == "sent",
                    NotificationDelivery.urgent.is_(False),
                    NotificationDelivery.sent_at > now - timedelta(hours=1),
                )
            )
            if (recent or 0) >= HOURLY_CAP:
                d.next_attempt_at = now + timedelta(hours=1)
                db.commit()
                continue
        n = db.get(Notification, d.notification_id)
        assert n is not None
        d.attempts += 1
        try:
            out = ADAPTERS[d.channel](db, d, n)
        except Exception as e:
            out = Outcome("failed", error=f"{type(e).__name__}: {str(e)[:200]}")
        if out.status == "failed" and d.attempts < MAX_ATTEMPTS:
            d.next_attempt_at = now + timedelta(minutes=2**d.attempts)
            d.last_error = out.error
        else:
            d.status, d.last_error, d.provider_ref = out.status, out.error, out.ref
            if out.status == "sent":
                d.sent_at = now
            done += 1
        db.commit()
    return done


def worker_main(argv: list[str] | None = None) -> int:
    """portal-notification-worker [--once] [--interval S]: deliver queued email/push notifications."""
    import argparse

    p = argparse.ArgumentParser(prog="portal-notification-worker")
    p.add_argument("--once", action="store_true")
    p.add_argument("--interval", type=float, default=5.0)
    args = p.parse_args(argv)
    while True:
        with get_sessionmaker()() as db:
            n = deliver_due(db)
        if n:
            print(f"delivered {n} notification(s)", flush=True)
        if args.once:
            return 0
        time.sleep(args.interval)


def trial_reminders(argv: list[str] | None = None) -> int:
    """portal-notification-trial-reminders: tell learners 3 days before a free trial ends (schedule daily).
    Idempotent per trial entitlement."""
    from portal_api.modules.access.models import Entitlement

    with get_sessionmaker()() as db:
        now = _now(db)
        rows = db.scalars(
            select(Entitlement).where(
                Entitlement.source == "trial",
                Entitlement.status == "active",
                Entitlement.ends_at > now,
                Entitlement.ends_at <= now + timedelta(days=3),
            )
        ).all()
        sent = 0
        for e in rows:
            if service.notify(
                db,
                e.user_id,
                "trial.ending",
                {"ends": service.local_time(db, e.user_id, e.ends_at)},
                dedupe_key=f"trial-ending:{e.id}",
                link="/account",
            ):
                sent += 1
        db.commit()
    print(f"trial-ending reminders queued: {sent}")
    return 0
