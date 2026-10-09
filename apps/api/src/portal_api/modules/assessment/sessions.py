"""Scheduled mock sessions (roadmap P09.S2.T3; SCHEDULE-01).

A session schedules a published exam-profile version for a shared window:

* `starts_at` — nobody can start earlier;
* `entry_closes_at` — the late-entry cutoff;
* `late_entry` — `fixed_end`: everyone's deadline is `starts_at` + duration, so late entrants get less time; or
  `full_duration`: each learner gets the full duration from their own start, capped at `window_closes_at`;
* `results_at` — when results and solutions are released (read live from the session, so staff can move it).
  Until then the result is withheld entirely (not just the keys, because per-question marks would reveal them).
  The submission receipt still confirms the work was saved.

Times are stored in UTC and shown in the session's `timezone` (default Asia/Karachi).

Accommodations give one learner extra minutes for one session, with a reason. They are explicit, audited and
applied to that learner's deadline only. A learner joins once per session (idempotent): joining builds the frozen mock
form from the session's pinned profile version, then starts the attempt. The time-limit policy is frozen into the
form, so later edits to the session never change an attempt already started.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, Literal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base
from portal_api.errors import Conflict, NotFound, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.identity.deps import Principal

LateEntry = Literal["fixed_end", "full_duration"]


class MockSession(Base):
    __tablename__ = "mock_session"
    __table_args__ = (
        CheckConstraint("late_entry in ('fixed_end','full_duration')", name="mock_session_late_entry"),
        CheckConstraint("status in ('scheduled','cancelled')", name="mock_session_status"),
        CheckConstraint(
            "entry_closes_at > starts_at and window_closes_at >= entry_closes_at", name="mock_session_window"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_profile_version.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(200))
    timezone: Mapped[str] = mapped_column(String(60), default="Asia/Karachi")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    entry_closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    results_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    late_entry: Mapped[str] = mapped_column(String(14), default="fixed_end")
    status: Mapped[str] = mapped_column(String(10), default="scheduled")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MockAccommodation(Base):
    __tablename__ = "mock_accommodation"
    __table_args__ = (UniqueConstraint("session_id", "user_id", name="uq_mock_accommodation"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mock_session.id", ondelete="RESTRICT"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    extra_minutes: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    granted_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _now(db: Session) -> datetime:
    now: datetime = db.execute(select(func.clock_timestamp())).scalar_one()
    return now


def schedule(
    db: Session,
    who: Principal,
    *,
    profile_code: str,
    title: str,
    starts_at: datetime,
    entry_closes_at: datetime,
    window_closes_at: datetime,
    results_at: datetime,
    late_entry: str,
    timezone: str,
) -> MockSession:
    from portal_api.modules.assessment.mocks import _published

    _, version = _published(db, profile_code)
    duration = timedelta(minutes=int(version.rules["duration_minutes"]))
    if not (starts_at < entry_closes_at <= window_closes_at):
        raise Unprocessable("The window must start, then close to late entry, then end, in that order.")
    if late_entry == "fixed_end" and window_closes_at < starts_at + duration:
        raise Unprocessable("With a fixed end the window must last at least the test's duration.")
    if results_at < window_closes_at:
        raise Unprocessable("Results can't be released before the window closes.")
    if starts_at <= _now(db):
        raise Unprocessable("Schedule sessions in the future.")
    s = MockSession(
        id=uuid.uuid4(),
        profile_version_id=version.id,
        title=title.strip(),
        timezone=timezone,
        starts_at=starts_at,
        entry_closes_at=entry_closes_at,
        window_closes_at=window_closes_at,
        results_at=results_at,
        late_entry=late_entry,
        created_by=who.user.id,
    )
    db.add(s)
    record(
        db,
        actor=who.user.id,
        action="mock_session.scheduled",
        target_type="mock_session",
        target_id=str(s.id),
        details={"profile": profile_code, "version": version.version, "starts_at": starts_at.isoformat()},
    )
    db.commit()
    db.refresh(s)
    return s


def accommodate(
    db: Session, who: Principal, session_id: uuid.UUID, user_id: uuid.UUID, minutes: int, reason: str
) -> None:
    s = db.get(MockSession, session_id)
    if s is None:
        raise NotFound("Session not found.")
    existing = db.scalar(
        select(MockAccommodation).where(MockAccommodation.session_id == s.id, MockAccommodation.user_id == user_id)
    )
    if existing is not None:
        existing.extra_minutes, existing.reason, existing.granted_by = minutes, reason.strip(), who.user.id
    else:
        db.add(
            MockAccommodation(
                session_id=s.id, user_id=user_id, extra_minutes=minutes, reason=reason.strip(), granted_by=who.user.id
            )
        )
    record(
        db,
        actor=who.user.id,
        action="mock_session.accommodation",
        target_type="mock_session",
        target_id=str(s.id),
        details={"learner": str(user_id), "extra_minutes": minutes, "reason": reason.strip()},
    )
    db.commit()


def cancel(db: Session, who: Principal, session_id: uuid.UUID, reason: str) -> MockSession:
    s = db.get(MockSession, session_id)
    if s is None:
        raise NotFound("Session not found.")
    if s.status == "cancelled":
        raise Conflict("This session is already cancelled.")
    if s.starts_at <= _now(db):
        raise Conflict("A session that has started can't be cancelled; learners keep their attempts.")
    s.status = "cancelled"
    record(
        db,
        actor=who.user.id,
        action="mock_session.cancelled",
        target_type="mock_session",
        target_id=str(s.id),
        details={"reason": reason.strip()},
    )
    db.commit()
    return s


def upcoming(db: Session) -> list[tuple[MockSession, Any, Any]]:
    from portal_api.modules.assessment.profiles import ExamProfile, ExamProfileVersion

    return [
        (s, p, v)
        for s, v, p in db.execute(
            select(MockSession, ExamProfileVersion, ExamProfile)
            .join(ExamProfileVersion, ExamProfileVersion.id == MockSession.profile_version_id)
            .join(ExamProfile, ExamProfile.id == ExamProfileVersion.profile_id)
            .where(MockSession.status == "scheduled", MockSession.window_closes_at > func.now())
            .order_by(MockSession.starts_at)
        ).all()
    ]


def join(db: Session, who: Principal, session_id: uuid.UUID) -> uuid.UUID:
    """Build (once) and start this learner's attempt for the session; returns the attempt ID."""
    from portal_api.modules.assessment import attempts, mocks
    from portal_api.modules.assessment.models import PracticeForm
    from portal_api.modules.assessment.profiles import ExamProfile, ExamProfileVersion

    s = db.get(MockSession, session_id)
    if s is None or s.status != "scheduled":
        raise NotFound("Session not found.")
    key = f"session-{s.id}"
    existing = db.scalar(
        select(PracticeForm).where(PracticeForm.owner_id == who.user.id, PracticeForm.idempotency_key == key)
    )
    if existing is None:
        now = _now(db)
        if now < s.starts_at:
            raise Conflict(
                "This mock hasn't started yet.", code_reason="NOT_STARTED", starts_at=s.starts_at.isoformat()
            )
        if now > s.entry_closes_at:
            raise Conflict("Late entry for this mock has closed.", code_reason="ENTRY_CLOSED")
        version = db.get(ExamProfileVersion, s.profile_version_id)
        assert version is not None
        profile = db.get(ExamProfile, version.profile_id)
        assert profile is not None
        extra = db.scalar(
            select(MockAccommodation.extra_minutes).where(
                MockAccommodation.session_id == s.id, MockAccommodation.user_id == who.user.id
            )
        )
        duration = timedelta(minutes=int(version.rules["duration_minutes"]))
        end = s.starts_at + duration if s.late_entry == "fixed_end" else min(now + duration, s.window_closes_at)
        seconds = int((end - now).total_seconds()) + int(extra or 0) * 60
        form = mocks.build_from(
            db,
            who,
            profile,
            version,
            idempotency_key=key,
            duration_s=max(seconds, 60),
            extra_scope={
                "session_id": str(s.id),
                "results_at": s.results_at.isoformat(),
                "late_entry": s.late_entry,
                "accommodation_minutes": int(extra or 0),
            },
            allow_scheduled=True,
        )
    else:
        form = existing
    attempt = attempts.start(db, who, form.id)
    return attempt.id
