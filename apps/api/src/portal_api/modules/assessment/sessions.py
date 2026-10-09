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
form from the session's pinned profile version, then starts the attempt.

**Absolute deadlines (OCT9-04).** The deadline is computed when the attempt really starts (`admit`), from the live
session: `fixed_end` → `starts_at` + duration; `full_duration` → min(start + duration, `window_closes_at`); plus the
learner's accommodation. Admission is rechecked at that moment, so a form saved before an interruption can't be
started after entry closes, and a retry never restarts the clock. No time left means no admission; remaining seconds
are never rounded up. An accommodation may run past `window_closes_at` (that is its purpose), but never past
`results_at`: the latest permitted deadline plus the late-write tolerance must be before the results release, so
common solutions are never shown while anyone may still write. With a fixed end, late entry must close before it.
Once started, an attempt's deadline never changes with later session edits.
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
    if late_entry == "fixed_end" and entry_closes_at >= starts_at + duration:
        raise Unprocessable("With a fixed end, late entry must close before the test ends.")
    tolerance = timedelta(milliseconds=int(version.rules.get("late_write_tolerance_ms", 0)))
    if results_at < window_closes_at or results_at < _latest_end(starts_at, window_closes_at, late_entry, duration) + (
        tolerance
    ):
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


def _latest_end(starts_at: datetime, window_closes_at: datetime, late_entry: str, duration: timedelta) -> datetime:
    """The latest deadline anyone can have before accommodations."""
    return starts_at + duration if late_entry == "fixed_end" else window_closes_at


def _rules(db: Session, s: MockSession) -> dict[str, Any]:
    from portal_api.modules.assessment.profiles import ExamProfileVersion

    version = db.get(ExamProfileVersion, s.profile_version_id)
    assert version is not None
    return dict(version.rules)


def accommodate(
    db: Session, who: Principal, session_id: uuid.UUID, user_id: uuid.UUID, minutes: int, reason: str
) -> None:
    s = db.get(MockSession, session_id)
    if s is None:
        raise NotFound("Session not found.")
    rules = _rules(db, s)
    latest = _latest_end(
        s.starts_at, s.window_closes_at, s.late_entry, timedelta(minutes=int(rules["duration_minutes"]))
    )
    if latest + timedelta(minutes=minutes, milliseconds=int(rules.get("late_write_tolerance_ms", 0))) > s.results_at:
        raise Unprocessable(
            "This much extra time would run past the results release. Move the results time later first.",
            code_reason="ACCOMMODATION_PAST_RESULTS",
        )
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
        _check_entry(s, now)
        version = db.get(ExamProfileVersion, s.profile_version_id)
        assert version is not None
        profile = db.get(ExamProfile, version.profile_id)
        assert profile is not None
        form = mocks.build_from(
            db,
            who,
            profile,
            version,
            idempotency_key=key,
            duration_s=int(version.rules["duration_minutes"]) * 60,  # nominal; the real deadline is set by `admit`
            extra_scope={
                "session_id": str(s.id),
                "results_at": s.results_at.isoformat(),
                "late_entry": s.late_entry,
            },
            allow_scheduled=True,
        )
    else:
        form = existing
    attempt = attempts.start(db, who, form.id)
    return attempt.id


def _check_entry(s: MockSession, now: datetime) -> None:
    if s.status != "scheduled":
        raise Conflict("This mock session was cancelled.", code_reason="ENTRY_CLOSED")
    if now < s.starts_at:
        raise Conflict("This mock hasn't started yet.", code_reason="NOT_STARTED", starts_at=s.starts_at.isoformat())
    if now > s.entry_closes_at:
        raise Conflict("Late entry for this mock has closed.", code_reason="ENTRY_CLOSED")


def admit(db: Session, form: Any, user_id: uuid.UUID, now: datetime) -> datetime:
    """The absolute deadline for starting this session form now, or a refusal (OCT9-04). Fails closed."""
    sid = (form.scope or {}).get("session_id")
    s = db.get(MockSession, uuid.UUID(str(sid))) if sid else None
    if s is None:
        raise Conflict("This mock session can't be found.", code_reason="ENTRY_CLOSED")
    _check_entry(s, now)
    rules = _rules(db, s)
    duration = timedelta(minutes=int(rules["duration_minutes"]))
    extra = db.scalar(
        select(MockAccommodation.extra_minutes).where(
            MockAccommodation.session_id == s.id, MockAccommodation.user_id == user_id
        )
    )
    end = s.starts_at + duration if s.late_entry == "fixed_end" else min(now + duration, s.window_closes_at)
    deadline = end + timedelta(minutes=int(extra or 0))
    if deadline <= now:
        raise Conflict("No time remains in this mock window.", code_reason="ENTRY_CLOSED")
    return deadline


# ------------------------------------------------------------------ result release policy (OCT9-01)
# One rule for every learner surface: result, reveal, progress, notebook, evidence (and so the study plan),
# notifications and the personal-data export. A form that belongs to a scheduled session is held until that session's
# *live* `results_at`. A session reference that can't be resolved fails closed: held, with no release time.


def held_forms(db: Session, user_id: uuid.UUID) -> dict[uuid.UUID, datetime | None]:
    """This learner's forms whose results are still held, mapped to their release time (None: unresolvable)."""
    from portal_api.modules.assessment.models import PracticeForm

    rows = db.execute(
        select(PracticeForm.id, PracticeForm.scope["session_id"].astext).where(
            PracticeForm.owner_id == user_id, PracticeForm.scope.has_key("session_id")
        )
    ).all()
    if not rows:
        return {}
    now = _now(db)
    ids: dict[uuid.UUID, uuid.UUID | None] = {}
    for form_id, raw in rows:
        try:
            ids[form_id] = uuid.UUID(str(raw))
        except ValueError:
            ids[form_id] = None
    release = dict(
        db.execute(
            select(MockSession.id, MockSession.results_at).where(
                MockSession.id.in_([s for s in ids.values() if s is not None])
            )
        ).all()
    )
    held: dict[uuid.UUID, datetime | None] = {}
    for form_id, sid in ids.items():
        at = release.get(sid) if sid is not None else None
        if at is None or at > now:
            held[form_id] = at
    return held


def require_released(db: Session, form: Any) -> None:
    """Raise RESULTS_PENDING if this form's results are still held."""
    scope = form.scope or {}
    if "session_id" not in scope:
        return
    held = held_forms(db, form.owner_id)
    if form.id in held:
        at = held[form.id]
        raise Conflict(
            "Your answers are saved. Results are released after the mock window closes.",
            code_reason="RESULTS_PENDING",
            available_at=at.isoformat() if at is not None else None,
        )
