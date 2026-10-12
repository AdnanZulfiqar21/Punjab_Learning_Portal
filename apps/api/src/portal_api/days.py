"""Calendar days as learners and staff in Pakistan read them (roadmap P12.S4.T3; DAYS-01).

The database runs in UTC, so its `current_date` and `date_trunc('day', ...)` start each day at 05:00 in Pakistan.
Between midnight and 05:00 a learner's "today" was still yesterday: a study plan counted one day too many and a
lesson opened before and after midnight counted as one day. Days a person sees, and days that count activity, use
Pakistan time instead (a learner's own day follows their timezone preference, Asia/Karachi by default). Instants are
still stored and compared in UTC.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

PLATFORM_TZ = "Asia/Karachi"


def local_date(at: datetime, tz: str = PLATFORM_TZ) -> date:
    """The calendar day an instant falls on in a timezone."""
    return at.astimezone(ZoneInfo(tz)).date()


def wall_clock(at: datetime, tz: str = PLATFORM_TZ) -> datetime:
    """An instant as a naive wall-clock time in a timezone, comparable with `day_of`/`week_of` values."""
    return at.astimezone(ZoneInfo(tz)).replace(tzinfo=None)


def learner_today(db: Session, user_id: uuid.UUID) -> date:
    """Today for this learner: the database clock in their timezone preference."""
    from portal_api.modules.notifications.service import preferences

    now: datetime = db.execute(select(func.now())).scalar_one()
    return local_date(now, preferences(db, user_id).timezone)


def day_of(column: Any) -> ColumnElement[Any]:
    """SQL: the start of the Pakistan day a timestamp falls on (a timestamp without timezone)."""
    return func.date_trunc("day", func.timezone(PLATFORM_TZ, column))


def week_of(column: Any) -> ColumnElement[Any]:
    """SQL: the start (Monday) of the Pakistan ISO week a timestamp falls on."""
    return func.date_trunc("week", func.timezone(PLATFORM_TZ, column))
