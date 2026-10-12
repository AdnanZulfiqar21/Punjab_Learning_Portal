"""The exam room during a mock (roadmap P10.S4.T3; EXAM-ROOM-01).

While a learner's mock attempt is open (active and before its cutoff), every route that could reveal answers or
explanations is refused with MOCK_IN_PROGRESS: new practice, review and mock tests, other attempts (opening,
answering, flagging, moving, submitting), other results, the mistake notebook and offline study packs. The running
mock itself works normally, and everything opens again once it is submitted or its time is up.

What this does not do: lessons stay readable, and a normal browser or phone can't stop someone opening a book,
another app or another device. Results stay a learner's own practice evidence; nothing here claims to prevent
cheating. Mock-only questions (P08.S3.T3) are the protection for patterns whose solutions are released late.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from portal_api.errors import Conflict
from portal_api.modules.assessment.models import Attempt, PracticeForm

MESSAGE = (
    "Your mock test is still running. Other tests, results, the mistake notebook and study packs open again when you "
    "submit it or its time is up."
)


def running_mock(db: Session, user_id: uuid.UUID) -> tuple[Attempt, PracticeForm] | None:
    from portal_api.modules.assessment.attempts import db_now

    row = db.execute(
        select(Attempt, PracticeForm)
        .join(PracticeForm, PracticeForm.id == Attempt.form_id)
        .where(
            Attempt.user_id == user_id,
            Attempt.status == "active",
            PracticeForm.kind == "mock",
            or_(Attempt.cutoff_at.is_(None), Attempt.cutoff_at > db_now(db)),
        )
        .order_by(Attempt.started_at.desc())
        .limit(1)
    ).first()
    return (row[0], row[1]) if row is not None else None


def _refuse(attempt: Attempt) -> Conflict:
    return Conflict(MESSAGE, code_reason="MOCK_IN_PROGRESS", attempt_id=str(attempt.id))


def guard(db: Session, user_id: uuid.UUID, *, attempt_id: uuid.UUID | None = None) -> None:
    """Refuse unless no mock is running, or the request is about the running mock's own attempt."""
    running = running_mock(db, user_id)
    if running is not None and running[0].id != attempt_id:
        raise _refuse(running[0])


def guard_form(db: Session, user_id: uuid.UUID, form_id: uuid.UUID) -> None:
    """Starting or resuming an attempt: only the running mock's own form."""
    running = running_mock(db, user_id)
    if running is not None and running[1].id != form_id:
        raise _refuse(running[0])


def guard_session(db: Session, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
    """Joining a scheduled mock: only the session the running mock belongs to."""
    running = running_mock(db, user_id)
    scope: dict[str, Any] = running[1].scope or {} if running is not None else {}
    if running is not None and scope.get("session_id") != str(session_id):
        raise _refuse(running[0])
