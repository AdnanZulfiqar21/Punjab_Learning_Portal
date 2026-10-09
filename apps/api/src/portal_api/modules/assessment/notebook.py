"""Mistake notebook and spaced review (roadmap P12.S3.T1-T3; NOTEBOOK-01).

**Collecting:** every question a learner answers wrongly in a submitted practice test, mock or review test becomes
(or refreshes) one notebook entry per question family. Unanswered questions are not mistakes. When a reviewed
correction voids a question (EXCLUDE or CREDIT_ALL), its entry stays in the notebook as `voided`, with the reason,
instead of disappearing.

**Spacing:** deterministic intervals of 1, 3, 7 and 14 days (`INTERVALS`).
* A wrong answer, first time or in review, resets the entry: due again after 1 day.
* A correct answer in a review test moves it to the next interval; after the last interval it is `mastered`.
* Each entry explains why it is due (when it was last missed or last reviewed, and the interval).
* At most `DAILY_CAP` entries are offered per review test. Missed days don't pile up: an overdue entry is simply due.

**Reviewing:** a review test is a frozen practice form (`kind="review"`) built from due entries of one class and
subject. It uses each family's current live question, preferring a variant other than the one originally missed, so
the original attempt stays exactly as it was.

Learners can add a private note to any entry.

**Derived by replay (OCT9-01, OCT9-02):** an entry's status, misses, interval and due date are never incremented in
place. They are recomputed for the affected question families by replaying the learner's genuine responses in the
order they were submitted (each attempt's `finalised_at`), using every attempt's *latest* score version. So:
* a score correction is not another practice session: unchanged answers keep their misses, interval and due date;
* wrong→correct, correct→wrong and void→restored corrections reconcile in the original chronology, including an old
  attempt corrected after newer reviews; replaying the same correction changes nothing;
* an entry that loses every mistake behind it is kept, `voided` with the reason, so private notes and history survive.
A scheduled mock whose results are still held (`sessions.held_forms`) is left out of the replay until its release;
`sync` applies released attempts once (`attempt.notebook_applied_at`). Replays for one learner are serialised with a
transaction-scoped advisory lock, so concurrent submissions and corrections can't duplicate entries.
"""

from __future__ import annotations

import random
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, String, Text, UniqueConstraint, func, select
from sqlalchemy import true as sa_true
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base
from portal_api.errors import Conflict, NotFound, Unprocessable
from portal_api.modules.assessment.models import Attempt, FormItem, PracticeForm
from portal_api.modules.content.models import Availability, ContentItem, ContentVersion

INTERVALS = (1, 3, 7, 14)  # days
DAILY_CAP = 20


class MistakeEntry(Base):
    __tablename__ = "mistake_entry"
    __table_args__ = (
        UniqueConstraint("user_id", "family_id", name="uq_mistake_entry_family"),
        CheckConstraint("status in ('open','mastered','voided')", name="mistake_entry_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_item.id", ondelete="RESTRICT"))
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_version.id", ondelete="RESTRICT"))
    source_attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempt.id", ondelete="RESTRICT"))
    position: Mapped[int] = mapped_column(SmallInteger)
    grade_number: Mapped[int] = mapped_column(SmallInteger)
    subject_code: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(10), default="open")
    void_reason: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text, default="")
    interval_index: Mapped[int] = mapped_column(SmallInteger, default=0)
    misses: Mapped[int] = mapped_column(SmallInteger, default=1)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_event: Mapped[str] = mapped_column(String(10), default="missed")  # missed | reviewed
    last_event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


NO_LONGER_A_MISTAKE = "Your answer was re-marked as correct after review, so this is no longer a mistake."
WITHDRAWN = "This question was withdrawn after academic review."


def _replay(events: list[tuple[datetime, str, dict[str, Any], FormItem, uuid.UUID]]) -> dict[str, Any] | None:
    """One family's derived state from its responses in submission order (None: never a counted mistake)."""
    st: dict[str, Any] | None = None
    for at, kind, row, fi, attempt_id in events:
        if row.get("treatment") in ("EXCLUDE", "CREDIT_ALL"):
            if st is not None and st["status"] != "voided":
                st["status"], st["void_reason"] = "voided", WITHDRAWN
            continue
        if row.get("correct") is False and row.get("chosen") is not None:
            if st is None:
                st = {"first": (attempt_id, fi), "misses": 0, "void_reason": None}
            elif st["status"] == "voided":
                continue
            st.update(status="open", interval_index=0, last_event="missed", last_event_at=at)
            st["misses"] += 1
            st["due_at"] = at + timedelta(days=INTERVALS[0])
        elif row.get("correct") is True and kind == "review" and st is not None and st["status"] == "open":
            nxt = st["interval_index"] + 1
            st["last_event"], st["last_event_at"] = "reviewed", at
            if nxt >= len(INTERVALS):
                st["status"] = "mastered"
            else:
                st["interval_index"], st["due_at"] = nxt, at + timedelta(days=INTERVALS[nxt])
    return st


def reconcile(db: Session, user_id: uuid.UUID, family_ids: set[uuid.UUID]) -> None:
    """Recompute these families' entries from the learner's released responses (inside the caller's transaction)."""
    from portal_api.modules.assessment.models import ScoreVersion
    from portal_api.modules.assessment.sessions import held_forms

    if not family_ids:
        return
    db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(f"notebook:{user_id}", 0))))
    held = held_forms(db, user_id)
    latest = (
        select(ScoreVersion.attempt_id, func.max(ScoreVersion.version).label("v"))
        .group_by(ScoreVersion.attempt_id)
        .subquery()
    )
    rows = db.execute(
        select(Attempt, PracticeForm.kind, ScoreVersion.items, FormItem)
        .join(PracticeForm, PracticeForm.id == Attempt.form_id)
        .join(FormItem, FormItem.form_id == Attempt.form_id)
        .join(latest, latest.c.attempt_id == Attempt.id)
        .join(ScoreVersion, (ScoreVersion.attempt_id == Attempt.id) & (ScoreVersion.version == latest.c.v))
        .where(
            Attempt.user_id == user_id,
            Attempt.status == "finalised",
            FormItem.family_id.in_(family_ids),
            Attempt.form_id.not_in(list(held)) if held else sa_true(),
        )
        .order_by(Attempt.finalised_at, Attempt.id, FormItem.position)
    ).all()
    events: dict[uuid.UUID, list[tuple[datetime, str, dict[str, Any], FormItem, uuid.UUID]]] = {}
    for attempt, kind, items, fi in rows:
        row = next((r for r in items if int(r["position"]) == fi.position), None)
        if row is not None and attempt.finalised_at is not None:
            events.setdefault(fi.family_id, []).append((attempt.finalised_at, kind, row, fi, attempt.id))
    existing = {
        e.family_id: e
        for e in db.scalars(
            select(MistakeEntry).where(MistakeEntry.user_id == user_id, MistakeEntry.family_id.in_(family_ids))
        )
    }
    for family_id in family_ids:
        st = _replay(events.get(family_id, []))
        entry = existing.get(family_id)
        if st is None:
            withdrawn = any(e[2].get("treatment") in ("EXCLUDE", "CREDIT_ALL") for e in events.get(family_id, []))
            if entry is not None:
                entry.status, entry.void_reason = "voided", WITHDRAWN if withdrawn else NO_LONGER_A_MISTAKE
            continue
        source_attempt, fi = st["first"]
        if entry is None:
            item = db.get(ContentItem, fi.item_id)
            assert item is not None
            entry = MistakeEntry(
                id=uuid.uuid4(),
                user_id=user_id,
                family_id=family_id,
                grade_number=item.grade_number,
                subject_code=item.subject_code,
                note="",
            )
            db.add(entry)
        entry.item_id, entry.version_id, entry.position = fi.item_id, fi.version_id, fi.position
        entry.source_attempt_id = source_attempt
        entry.status, entry.void_reason = st["status"], st["void_reason"]
        entry.interval_index, entry.misses, entry.due_at = st["interval_index"], st["misses"], st["due_at"]
        entry.last_event, entry.last_event_at = st["last_event"], st["last_event_at"]
    db.flush()


def apply_attempt(db: Session, attempt: Attempt, now: datetime) -> None:
    """Reflect a finalised (or re-scored) attempt in the notebook, unless its results are still held."""
    from portal_api.modules.assessment.sessions import held_forms

    if attempt.form_id in held_forms(db, attempt.user_id):
        return  # applied by `sync` once released
    families = set(db.scalars(select(FormItem.family_id).where(FormItem.form_id == attempt.form_id)))
    reconcile(db, attempt.user_id, families)
    attempt.notebook_applied_at = attempt.notebook_applied_at or now
    db.flush()


def sync(db: Session, user_id: uuid.UUID) -> None:
    """Apply finalised attempts not yet reflected (scheduled mocks whose results were released since); commits."""
    from portal_api.modules.assessment.sessions import held_forms

    pending = list(
        db.scalars(
            select(Attempt).where(
                Attempt.user_id == user_id, Attempt.status == "finalised", Attempt.notebook_applied_at.is_(None)
            )
        )
    )
    if not pending:
        return
    held = held_forms(db, user_id)
    ready = [a for a in pending if a.form_id not in held]
    if not ready:
        return
    now = db.execute(select(func.now())).scalar_one()
    for a in ready:
        apply_attempt(db, a, now)
    db.commit()


def why(entry: MistakeEntry, now: datetime) -> str:
    if entry.status == "voided":
        return entry.void_reason or "Withdrawn after review."
    if entry.status == "mastered":
        return "Answered correctly at every review interval."
    days = INTERVALS[entry.interval_index]
    verb = "missed" if entry.last_event == "missed" else "answered correctly in review"
    state = "due now" if entry.due_at <= now else f"due on {entry.due_at:%d %b %Y}"
    return f"{verb.capitalize()} on {entry.last_event_at:%d %b %Y}; reviewed again after {days} day(s) ({state})."


def entries(db: Session, user_id: uuid.UUID) -> list[MistakeEntry]:
    sync(db, user_id)
    return list(
        db.scalars(
            select(MistakeEntry)
            .where(MistakeEntry.user_id == user_id)
            .order_by(MistakeEntry.status, MistakeEntry.due_at)
            .limit(500)
        )
    )


def set_note(db: Session, user_id: uuid.UUID, entry_id: uuid.UUID, note: str) -> MistakeEntry:
    e = db.get(MistakeEntry, entry_id)
    if e is None or e.user_id != user_id:
        raise NotFound("Notebook entry not found.")
    e.note = note.strip()
    db.commit()
    db.refresh(e)
    return e


def _live_variant(
    db: Session, family_id: uuid.UUID, avoid_version: uuid.UUID
) -> tuple[ContentItem, ContentVersion] | None:
    rows = db.execute(
        select(ContentItem, ContentVersion)
        .join(ContentVersion, ContentVersion.id == ContentItem.published_version_id)
        .where(
            func.coalesce(ContentItem.family_id, ContentItem.id) == family_id,
            ContentItem.kind == "mcq",
            ContentItem.availability == Availability.live.value,
        )
    ).all()
    if not rows:
        return None
    others = [(i, v) for i, v in rows if v.id != avoid_version]  # prefer a variant the learner hasn't seen here
    pick = sorted(others or rows, key=lambda iv: str(iv[0].id))[0]
    return pick[0], pick[1]


def build_review(db: Session, who: Any, *, grade: int, subject: str, count: int, idempotency_key: str) -> PracticeForm:
    from portal_api.modules.access import service as access

    existing = db.scalar(
        select(PracticeForm).where(
            PracticeForm.owner_id == who.user.id, PracticeForm.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        if existing.kind != "review":
            raise Conflict("This request key was already used for a different test.")
        return existing
    access.require_access(db, who.user.id, purpose="Review tests")
    sync(db, who.user.id)
    now = db.execute(select(func.now())).scalar_one()
    due = db.scalars(
        select(MistakeEntry)
        .where(
            MistakeEntry.user_id == who.user.id,
            MistakeEntry.status == "open",
            MistakeEntry.grade_number == grade,
            MistakeEntry.subject_code == subject,
            MistakeEntry.due_at <= now,
        )
        .order_by(MistakeEntry.due_at)
        .limit(min(count, DAILY_CAP))
    ).all()
    chosen: list[tuple[MistakeEntry, tuple[ContentItem, ContentVersion]]] = []
    for e in due:
        iv = _live_variant(db, e.family_id, e.version_id)
        if iv is not None:  # a question no longer live can't be reviewed
            chosen.append((e, iv))
    if not chosen:
        raise Unprocessable("Nothing is due for review in this class and subject right now.", code_reason="NOTHING_DUE")
    seed = secrets.randbits(62)
    rng = random.Random(seed)  # noqa: S311 - reproducible option order from a stored seed, not a secret
    form = PracticeForm(
        id=uuid.uuid4(),
        owner_id=who.user.id,
        idempotency_key=idempotency_key,
        request_hash="review",
        kind="review",
        grade_number=grade,
        subject_code=subject,
        scope={"mode": "review", "entries": [str(e.id) for e, _ in chosen]},
        seed=seed,
        question_count=len(chosen),
        duration_s=None,
        late_write_tolerance_ms=0,
        feedback_mode="deferred",
        negative_marks=0,
        invalid_item_treatment="EXCLUDE",
    )
    db.add(form)
    for position, (e, (item, version)) in enumerate(chosen, start=1):
        option_ids = [o["id"] for o in version.body["options"]]
        if version.body.get("shuffle_options", True):
            rng.shuffle(option_ids)
        db.add(
            FormItem(
                form_id=form.id,
                position=position,
                item_id=item.id,
                family_id=e.family_id,
                version_id=version.id,
                marks=int(version.body.get("marks", 1)),
                option_order=option_ids,
            )
        )
    db.commit()
    db.refresh(form)
    return form
