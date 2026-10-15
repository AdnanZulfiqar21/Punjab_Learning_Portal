"""Honest learner comparisons for fixed forms (roadmap §6.6 "Peer cohort", P12.S2.T3, AC62; COMPARISON-01).

Only a scheduled session's fixed form (FIXED-FORMS-01) is compared: every participant answered exactly the same
question versions under the same scoring rule. Practice tests and practice mocks are varied per learner and are never
compared, and forms built before a session had a master aren't either.

**Membership.** One attempt per eligible learner account, the earliest qualifying one (a learner has one form, so one
attempt, per session; retakes elsewhere never add members). Eligible: an active learner account (no staff role, not a
development/test account), the attempt finalised within the `WINDOW` before the snapshot, and its latest score scored
(void attempts and NOT_SCORABLE results are left out). Learners with an accommodation are compared only with each
other (`timing_group`).

**Comparable scores.** Every member's latest score must use the current scoring policy and the form's current
effective correction set (§5.7). While a correction is still being applied, or a submission is still being scored,
the snapshot is `pending` and no percentile is shown: scores from before and after a correction are never mixed.

**Threshold.** At least `MIN_LEARNERS` distinct learner accounts; otherwise `too_few`, and the learner is told about
the sample limitation instead of getting a percentile.

**Percentile.** 100 * (members with a lower score + 0.5 * members with an equal score) / N, the learner included,
shown to one decimal with N, the window, the tie rule and the snapshot version. Distinct accounts are not proof of
distinct people, and the cohort is not a national sample; the learner is told so.

**Snapshots.** `portal-comparison-snapshots` builds one atomic row per session and timing group (members read in one
statement and written in one transaction) once results are released, and again whenever its inputs change. Readers use
the latest snapshot only; a learner whose score changed after it is told the comparison is being updated.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import uuid
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    and_,
    exists,
    func,
    or_,
    select,
    true,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.budget import process_class
from portal_api.db import Base
from portal_api.modules.assessment import scoring
from portal_api.modules.assessment.models import SCORING_POLICY_VERSION, Attempt, PracticeForm, ScoreVersion
from portal_api.modules.assessment.sessions import MockAccommodation, MockSession

log = logging.getLogger("portal.assessment.cohorts")

MIN_LEARNERS = 200
WINDOW = timedelta(days=90)
TimingGroup = Literal["standard", "accommodated"]
State = Literal["published", "too_few", "pending", "not_included"]

TIE_RULE = (
    "The percentage of learners compared who scored below you, plus half of those with the same score as you "
    "(you included). Equal scores count half."
)
LIMITS = (
    "Each learner account counts once, with its first result for this test. Accounts are not proof of distinct "
    "people, and the learners compared are not a national sample."
)
GROUP_TEXT = {
    "standard": "Learners who took this test in the standard time.",
    "accommodated": "Learners given extra time are compared only with each other.",
}
STATE_TEXT = {
    "preparing": "The comparison for this test is being prepared. Check back later.",
    "too_few": f"No comparison yet: fewer than {MIN_LEARNERS} learners have a comparable result for this test.",
    "pending": (
        "A score correction is being applied to this test. The comparison is hidden until every result is updated, "
        "so scores from before and after the correction are never mixed."
    ),
    "updating": "Your score changed after the comparison was made. It is shown again once the comparison is updated.",
    "not_yet": "Your result isn't in the comparison yet. It is added the next time the comparison is updated.",
    "not_scorable": "This result couldn't be scored, so it isn't compared.",
    "not_learner": "Staff and test accounts aren't compared with learners.",
}


class ComparisonSnapshot(Base):
    """One atomic, versioned comparison for a session's fixed form and timing group."""

    __tablename__ = "comparison_snapshot"
    __table_args__ = (
        UniqueConstraint("session_id", "timing_group", "version", name="uq_comparison_snapshot_version"),
        CheckConstraint("state in ('published','too_few','pending')", name="comparison_snapshot_state"),
        CheckConstraint("timing_group in ('standard','accommodated')", name="comparison_snapshot_timing_group"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mock_session.id", ondelete="RESTRICT"), index=True)
    timing_group: Mapped[str] = mapped_column(String(12))
    version: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(10))
    learners: Mapped[int] = mapped_column(Integer)  # distinct eligible learner accounts with a comparable score
    maximum: Mapped[int | None] = mapped_column(Integer)
    scoring_policy_version: Mapped[int] = mapped_column(SmallInteger)
    adjudication_hash: Mapped[str] = mapped_column(String(64))  # the form's effective correction set
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    inputs_hash: Mapped[str] = mapped_column(String(64))  # unchanged inputs never make a new version
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ComparisonMember(Base):
    """A member of a published snapshot: the attempt and the exact score version it was compared with."""

    __tablename__ = "comparison_member"
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comparison_snapshot.id", ondelete="RESTRICT"), primary_key=True
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempt.id", ondelete="RESTRICT"), primary_key=True)
    score_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("score_version.id", ondelete="RESTRICT"))
    raw: Mapped[int] = mapped_column(Integer)


def _now(db: Session) -> datetime:
    now: datetime = db.execute(select(func.clock_timestamp())).scalar_one()
    return now


def _fixed_forms(master_id: uuid.UUID) -> Any:
    """The session's master form and its exact copies; never a form built before the session had a master."""
    return or_(PracticeForm.id == master_id, PracticeForm.scope["fixed_from"].astext == str(master_id))


def _test_issuer() -> str:
    """Accounts from this issuer are development/test accounts and are never compared."""
    from portal_api.config import get_settings

    return get_settings().dev_auth_issuer


def _eligible_learner() -> Any:
    from portal_api.modules.identity.models import AppUser, StaffRoleGrant

    staff = exists().where(StaffRoleGrant.user_id == AppUser.id, StaffRoleGrant.revoked_at.is_(None))
    return and_(AppUser.status == "active", AppUser.issuer != _test_issuer(), ~staff)


def _latest_score() -> Any:
    """Each attempt's latest score version (one indexed lookup per attempt)."""
    return (
        select(ScoreVersion)
        .where(ScoreVersion.attempt_id == Attempt.id)
        .order_by(ScoreVersion.version.desc())
        .limit(1)
        .lateral()
    )


def _latest(db: Session, s: MockSession, group: str) -> ComparisonSnapshot | None:
    return db.scalar(
        select(ComparisonSnapshot)
        .where(ComparisonSnapshot.session_id == s.id, ComparisonSnapshot.timing_group == group)
        .order_by(ComparisonSnapshot.version.desc())
        .limit(1)
    )


def build(db: Session, s: MockSession) -> list[ComparisonSnapshot]:
    """Build the session's snapshots whose inputs changed; returns the new ones. Each commits on its own."""
    from portal_api.modules.assessment.adjudications import effective_for_form
    from portal_api.modules.identity.models import AppUser

    if s.master_form_id is None:
        return []
    master = db.get(PracticeForm, s.master_form_id)
    assert master is not None
    # The expected set is read first: a correction landing after this makes some scores newer than it, which reads as
    # pending (hidden), never as a mixed comparison.
    digest = scoring.adjudication_hash(effective_for_form(db, master))
    now = _now(db)
    since = now - WINDOW
    latest = _latest_score()
    rows = db.execute(  # one statement, so one consistent view of every member
        select(
            Attempt.id,
            Attempt.user_id,
            latest.c.id,
            latest.c.status,
            latest.c.raw,
            latest.c.maximum,
            latest.c.scoring_policy_version,
            latest.c.adjudication_hash,
            MockAccommodation.id.is_not(None),
        )
        .join(PracticeForm, PracticeForm.id == Attempt.form_id)
        .join(AppUser, AppUser.id == Attempt.user_id)
        .outerjoin(latest, true())
        .outerjoin(
            MockAccommodation,
            and_(MockAccommodation.session_id == s.id, MockAccommodation.user_id == Attempt.user_id),
        )
        .where(
            _fixed_forms(master.id),
            _eligible_learner(),
            Attempt.status == "finalised",
            Attempt.finalised_at > since,
            Attempt.finalised_at <= now,
        )
        .order_by(Attempt.user_id, Attempt.started_at, Attempt.id)
    ).all()
    db.rollback()
    groups: dict[str, list[Any]] = {"standard": [], "accommodated": []}
    for r in rows:
        groups["accommodated" if r[8] else "standard"].append(r)
    made = []
    for group, rs in groups.items():
        previous = _latest(db, s, group)
        if not rs and previous is None:
            continue  # nobody in this timing group, now or before
        pending = any(r[2] is None or (r[6], r[7]) != (SCORING_POLICY_VERSION, digest) for r in rs)
        members: dict[uuid.UUID, Any] = {}
        for r in rs:
            if r[3] == "scored" and r[1] not in members:  # the earliest qualifying attempt per account
                members[r[1]] = r
        maxima = {r[5] for r in members.values()}
        if pending or len(maxima) > 1:
            state = "pending"
        elif len(members) < MIN_LEARNERS:
            state = "too_few"
        else:
            state = "published"
        inputs = hashlib.sha256(
            json.dumps(
                [state, SCORING_POLICY_VERSION, digest, sorted(f"{r[0]}:{r[2]}" for r in members.values())]
            ).encode()
        ).hexdigest()
        if previous is not None and previous.inputs_hash == inputs:
            continue
        snap = ComparisonSnapshot(
            id=uuid.uuid4(),
            session_id=s.id,
            timing_group=group,
            version=(previous.version if previous else 0) + 1,
            state=state,
            learners=len(members),
            maximum=next(iter(maxima)) if len(maxima) == 1 else None,
            scoring_policy_version=SCORING_POLICY_VERSION,
            adjudication_hash=digest,
            window_start=since,
            window_end=now,
            inputs_hash=inputs,
        )
        db.add(snap)
        db.flush()
        if state == "published":
            db.add_all(
                ComparisonMember(snapshot_id=snap.id, attempt_id=r[0], score_version_id=r[2], raw=r[4])
                for r in members.values()
            )
        try:
            db.commit()
        except IntegrityError:  # another builder wrote this version first; its snapshot is used
            db.rollback()
            continue
        made.append(snap)
    return made


def refresh(db: Session) -> int:
    """Rebuild the snapshots of every session whose results are released and still inside the window."""
    now = _now(db)
    due = list(
        db.scalars(
            select(MockSession).where(
                MockSession.master_form_id.is_not(None),
                MockSession.status == "scheduled",
                MockSession.results_at <= now,
                MockSession.results_at > now - WINDOW,
            )
        )
    )
    db.rollback()
    return sum(len(build(db, s)) for s in due)


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def for_attempt(db: Session, attempt: Attempt, form: PracticeForm, score: ScoreVersion) -> dict[str, Any] | None:
    """How this released result compares, or None when its form isn't a session's fixed form."""
    from portal_api.modules.identity.models import AppUser

    sid = (form.scope or {}).get("session_id")
    if not sid or (form.scope or {}).get("form_type") != "fixed":
        return None
    s = db.get(MockSession, uuid.UUID(sid))
    if s is None or s.master_form_id is None:
        return None
    if form.id != s.master_form_id and (form.scope or {}).get("fixed_from") != str(s.master_form_id):
        return None
    accommodated = db.scalar(
        select(MockAccommodation.id).where(
            MockAccommodation.session_id == s.id, MockAccommodation.user_id == attempt.user_id
        )
    )
    group = "accommodated" if accommodated else "standard"
    out: dict[str, Any] = {"timing_group": group, "group": GROUP_TEXT[group], "tie_rule": TIE_RULE, "limits": LIMITS}

    def hidden(state: State, why: str, snap: ComparisonSnapshot | None = None) -> dict[str, Any]:
        return {**out, "state": state, "message": STATE_TEXT[why], "version": snap.version if snap else None}

    learner = db.scalar(select(AppUser.id).where(AppUser.id == attempt.user_id, _eligible_learner()))
    if learner is None:
        return hidden("not_included", "not_learner")
    if score.status != "scored":
        return hidden("not_included", "not_scorable")
    snap = _latest(db, s, group)
    if snap is None:
        return hidden("pending", "preparing")
    if snap.state != "published":
        return hidden(snap.state, snap.state, snap)  # type: ignore[arg-type]
    member = db.get(ComparisonMember, (snap.id, attempt.id))
    if member is None:
        return hidden("pending", "not_yet", snap)
    if member.score_version_id != score.id:
        return hidden("pending", "updating", snap)
    lower, equal = db.execute(
        select(
            func.count().filter(ComparisonMember.raw < member.raw),
            func.count().filter(ComparisonMember.raw == member.raw),
        ).where(ComparisonMember.snapshot_id == snap.id)
    ).one()
    percentile = _round(Decimal(100) * (Decimal(lower) + Decimal(equal) / 2) / Decimal(snap.learners))
    return {
        **out,
        "state": "published",
        "message": f"Your percentile among {snap.learners} learners who took this same test.",
        "percentile": percentile,
        "learners": snap.learners,
        "window_start": snap.window_start,
        "window_end": snap.window_end,
        "version": snap.version,
    }


@process_class("bulk")
def main(argv: list[str] | None = None) -> int:
    """`portal-comparison-snapshots`: one pass; schedule it every few minutes."""
    from portal_api.budget import bulk_paused_now
    from portal_api.db import get_sessionmaker

    if why := bulk_paused_now():  # POOL-CAPS-01: the next scheduled run does it
        print(f"skipped: {why}", flush=True)
        return 0
    with get_sessionmaker()() as db:
        made = refresh(db)
    print(f"built {made} comparison snapshot(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
