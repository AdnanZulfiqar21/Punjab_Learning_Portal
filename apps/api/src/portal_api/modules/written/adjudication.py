"""Rubric adjudications across attempts (W06.S2.T3; §20.10; WA-AC26/64/77/78).

A rubric correction is first made through the editorial workflow: a new rubric version is drafted, reviewed and
published, and from then on new forms use it. Applying it to work already started or marked is a separate, historical
decision: an academic adjudicator records a :class:`RubricAdjudication` naming the superseded rubric versions it
corrects, the corrected (currently published) version and a reason. The adjudication never edits evidence, an earlier
score version or the original form; it changes which rubric is the *effective marking basis* for affected questions.

Effective set. Adjudications chain (A -> B, then B -> C), and an adjudication that changes the target for a version
already covered must explicitly supersede the earlier one. The effective rubric of a question is the end of that chain,
so every run applies the complete approved set at once and two jobs for the same attempt converge on one result.

Compatible denominators. A rubric correction must keep every slot's maximum. A different total is a question change,
not a rubric correction, and is refused.

Regrade per attempt, bounded and resumable (one short transaction per attempt; a ``RubricRegrade`` row per adjudication
and attempt is the checkpoint, so re-running never repeats work):

* scored question, scoring basis unchanged (criteria, maxima, levels, groups, dependencies and descriptions identical;
  only reviewer notes such as expected concepts differ): the human marks are carried forward onto the corrected rubric
  in a new released version labelled SYSTEM / regrade, recording the compatibility evidence. Marks don't change.
* scored question whose scoring basis changed: never recomputed by machine. A ``regrade`` review case is opened for a
  teacher to re-mark it under the corrected rubric; the current result stays until that teacher releases. If an open
  case (e.g. a recheck) already covers the question, that case is re-targeted instead (its version is bumped so a stale
  save conflicts).
* pending, unavailable or not yet marked: the corrected rubric becomes the target for any later marking.

Every affected learner gets one notice per adjudication. Nothing here consumes or releases allowance.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base
from portal_api.errors import Conflict, Forbidden, NotFound, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.content import written as wq
from portal_api.modules.content.models import Availability, ContentItem, ContentVersion, VersionStatus
from portal_api.modules.content.workflow import roles_in_scope
from portal_api.modules.identity.deps import Principal
from portal_api.modules.identity.permissions import Permission, permissions_for
from portal_api.modules.written.models import WrittenAttempt, WrittenForm, WrittenFormItem

MAX_CHAIN = 20
# Fields of a criterion that decide a mark. Equal on both sides means a human decision stays valid as recorded.
SCORING_FIELDS = ("subpart_id", "description", "max_units", "levels", "depends_on", "alternative_group")
RUBRIC_SCORING_FIELDS = (
    "increment_units",
    "alternative_routes",
    "consequential_error_rule",
    "units_rule",
    "crossed_out_rule",
)


class RubricAdjudication(Base):
    __tablename__ = "written_rubric_adjudication"
    __table_args__ = (CheckConstraint("status in ('active','superseded')", name="written_adjudication_status"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rubric_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_item.id", ondelete="RESTRICT"), index=True)
    grade_number: Mapped[int] = mapped_column(SmallInteger)
    subject_code: Mapped[str] = mapped_column(String(40))
    from_version_ids: Mapped[list[str]] = mapped_column(JSONB)  # superseded rubric versions it corrects
    to_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_version.id", ondelete="RESTRICT"))
    reason: Mapped[str] = mapped_column(Text)
    # Computed, never client-supplied: per corrected version, the criterion diff and whether marks may carry forward.
    compatibility: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(10), default="active")
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("written_rubric_adjudication.id", ondelete="RESTRICT")
    )
    approved_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RubricRegrade(Base):
    """Checkpoint and outcome of one adjudication for one attempt. ``deferred`` is retried by the next run."""

    __tablename__ = "written_rubric_regrade"
    __table_args__ = (
        UniqueConstraint("adjudication_id", "attempt_id", name="uq_written_regrade"),
        CheckConstraint("status in ('done','deferred')", name="written_regrade_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    adjudication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("written_rubric_adjudication.id", ondelete="RESTRICT"), index=True
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_attempt.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(10), default="done")
    outcomes: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict)  # position -> carried|review|...|current
    score_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("written_score_version.id", ondelete="RESTRICT")
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("written_review_case.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RubricTarget(Base):
    """The effective rubric for one question of one attempt after adjudication (absent: the form's pinned rubric)."""

    __tablename__ = "written_rubric_target"
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("written_attempt.id", ondelete="RESTRICT"), primary_key=True
    )
    position: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    rubric_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_version.id", ondelete="RESTRICT"))
    adjudication_ids: Mapped[list[str]] = mapped_column(JSONB)  # the chain applied, in order
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WrittenNotice(Base):
    """A learner notice about a change to a result. One per attempt, cause and kind (deduplicated by the database)."""

    __tablename__ = "written_notice"
    __table_args__ = (
        Index("uq_written_notice", "attempt_id", "cause_id", "kind", unique=True),
        CheckConstraint("kind in ('rubric_correction')", name="written_notice_kind"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_attempt.id", ondelete="RESTRICT"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    cause_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(String(30))
    positions: Mapped[list[int]] = mapped_column(JSONB)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ------------------------------------------------------------------ compatibility
def _criteria(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    r, _ = wq.parse_rubric(body)
    assert r is not None
    return {c.id: {f: getattr(c, f) for f in SCORING_FIELDS} for c in r.criteria}


def compatibility(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Criterion-level diff between two rubric bodies and whether human marks under ``old`` stay valid under ``new``."""
    a, b = _criteria(old), _criteria(new)
    criteria = {}
    for cid in sorted(set(a) | set(b)):
        if cid not in b:
            criteria[cid] = "removed"
        elif cid not in a:
            criteria[cid] = "added"
        else:
            criteria[cid] = "unchanged" if a[cid] == b[cid] else "changed"
    rubric_fields = [f for f in RUBRIC_SCORING_FIELDS if old.get(f) != new.get(f)]
    return {
        "criteria": criteria,
        "rubric_fields_changed": rubric_fields,
        "carry_forward": all(v == "unchanged" for v in criteria.values()) and not rubric_fields,
    }


def _slot_totals(body: dict[str, Any]) -> dict[str, int]:
    r, _ = wq.parse_rubric(body)
    assert r is not None
    return {str(k): v for k, v in wq.slot_totals(r).items()}


# ------------------------------------------------------------------ authority
def _may_adjudicate(db: Session, who: Principal, grade: int, subject: str) -> bool:
    return Permission.adjudicate in permissions_for(roles_in_scope(db, who.user.id, grade, subject))


def create(
    db: Session,
    who: Principal,
    *,
    rubric_item_id: uuid.UUID,
    reason: str,
    from_version_ids: list[uuid.UUID] | None = None,
    supersedes_id: uuid.UUID | None = None,
) -> RubricAdjudication:
    item = db.get(ContentItem, rubric_item_id)
    if item is None or item.kind != "rubric":
        raise NotFound("Rubric not found.")
    if not _may_adjudicate(db, who, item.grade_number, item.subject_code):
        raise Forbidden("Only an academic adjudicator for this class and subject can apply a rubric correction.")
    if len(reason.strip()) < 20:
        raise Unprocessable("Explain the correction and why it applies to work already marked (20+ characters).")
    if item.availability != Availability.live.value or item.published_version_id is None:
        raise Unprocessable("Publish the corrected rubric first; only a live, published rubric can be applied.")
    to = db.get(ContentVersion, item.published_version_id)
    assert to is not None
    qv = str(to.body.get("question_version_id"))
    candidates = {
        str(v.id): v
        for v in db.scalars(
            select(ContentVersion).where(
                ContentVersion.item_id == item.id, ContentVersion.status == VersionStatus.superseded.value
            )
        )
        if str(v.body.get("question_version_id")) == qv
    }
    chosen = [str(v) for v in from_version_ids] if from_version_ids else sorted(candidates)
    unknown = sorted(set(chosen) - set(candidates))
    if unknown:
        raise Unprocessable(
            "Only earlier published versions of this rubric for the same question can be corrected.", errors=unknown
        )
    if not chosen:
        raise Unprocessable(
            "This rubric has no earlier published version to correct.", code_reason="NOTHING_TO_CORRECT"
        )
    compat: dict[str, Any] = {}
    for vid in chosen:
        old = candidates[vid]
        if _slot_totals(old.body) != _slot_totals(to.body):
            raise Unprocessable(
                f"Version {old.number} and the corrected rubric award different maxima. A different total is a "
                "question change, not a rubric correction.",
                code_reason="INCOMPATIBLE_DENOMINATOR",
            )
        compat[vid] = {"number": old.number, **compatibility(old.body, to.body)}
    # A superseding correction names the one it replaces (§5.7): two active corrections never claim one version.
    # Creations for one rubric are serialised so two can't both see "nothing active" and overlap.
    db.execute(select(func.pg_advisory_xact_lock(item.id.int & 0x7FFFFFFFFFFFFFFF)))
    overlapping = [
        a
        for a in db.scalars(
            select(RubricAdjudication)
            .where(RubricAdjudication.rubric_item_id == item.id, RubricAdjudication.status == "active")
            .with_for_update()
        )
        if set(a.from_version_ids) & set(chosen)
    ]
    if overlapping and (supersedes_id is None or {a.id for a in overlapping} != {supersedes_id}):
        raise Conflict(
            "An active correction already covers these versions; supersede it explicitly.",
            code_reason="SUPERSEDE_REQUIRED",
            active=[str(a.id) for a in overlapping],
        )
    if supersedes_id is not None and not overlapping:
        raise Unprocessable("The correction to supersede isn't active for these versions.")
    adj = RubricAdjudication(
        id=uuid.uuid4(),
        rubric_item_id=item.id,
        grade_number=item.grade_number,
        subject_code=item.subject_code,
        from_version_ids=chosen,
        to_version_id=to.id,
        reason=reason.strip()[:2000],
        compatibility=compat,
        supersedes_id=supersedes_id,
        approved_by=who.user.id,
    )
    db.add(adj)
    for a in overlapping:
        a.status = "superseded"
    db.flush()
    record(
        db,
        actor=who.user.id,
        action="written.rubric_adjudicated",
        target_type="content_item",
        target_id=str(item.id),
        details={
            "adjudication": str(adj.id),
            "from": chosen,
            "to": str(to.id),
            "supersedes": str(supersedes_id) if supersedes_id else None,
            "carry_forward": {v: c["carry_forward"] for v, c in compat.items()},
        },
    )
    db.commit()
    db.refresh(adj)
    return adj


def get(db: Session, who: Principal, adjudication_id: uuid.UUID) -> RubricAdjudication:
    adj = db.get(RubricAdjudication, adjudication_id)
    if adj is None or not _may_adjudicate(db, who, adj.grade_number, adj.subject_code):
        raise NotFound("Correction not found.")
    return adj


def visible(db: Session, who: Principal) -> list[RubricAdjudication]:
    rows = db.scalars(select(RubricAdjudication).order_by(RubricAdjudication.approved_at.desc()).limit(200))
    return [a for a in rows if _may_adjudicate(db, who, a.grade_number, a.subject_code)]


# ------------------------------------------------------------------ effective set
def _active_for_item(db: Session, rubric_item_id: uuid.UUID) -> list[RubricAdjudication]:
    return list(
        db.scalars(
            select(RubricAdjudication).where(
                RubricAdjudication.rubric_item_id == rubric_item_id, RubricAdjudication.status == "active"
            )
        )
    )


def chain(active: list[RubricAdjudication], version_id: str) -> tuple[str, list[str]]:
    """Follow the active corrections from a rubric version to its effective version (the complete approved set)."""
    applied: list[str] = []
    current = version_id
    for _ in range(MAX_CHAIN):
        nxt = next((a for a in active if current in a.from_version_ids), None)
        if nxt is None or str(nxt.id) in applied:
            break
        applied.append(str(nxt.id))
        current = str(nxt.to_version_id)
    return current, applied


def targets(db: Session, attempt_id: uuid.UUID) -> dict[int, uuid.UUID]:
    """Effective rubric overrides for an attempt's questions (used by marking and results)."""
    return {
        t.position: t.rubric_version_id
        for t in db.scalars(select(RubricTarget).where(RubricTarget.attempt_id == attempt_id))
    }


def _current_rubrics(db: Session, attempt: WrittenAttempt) -> dict[int, str]:
    form = db.get(WrittenForm, attempt.form_id)
    assert form is not None
    over = targets(db, attempt.id)
    return {fi.position: str(over.get(fi.position, fi.rubric_version_id)) for fi in form.items}


def _affected(db: Session, adj: RubricAdjudication, attempt: WrittenAttempt) -> dict[int, tuple[str, str, list[str]]]:
    """Questions of this attempt whose effective rubric changes through ``adj``.

    Returns position -> (current rubric, effective target, chain of corrections applied)."""
    active = _active_for_item(db, adj.rubric_item_id)
    out = {}
    for pos, current in _current_rubrics(db, attempt).items():
        target, applied = chain(active, current)
        if str(adj.id) in applied and target != current:
            out[pos] = (current, target, applied)
    return out


def _candidate_attempts(db: Session, adj: RubricAdjudication) -> Any:
    """Attempts that may be affected: any form item or override on a version this correction (or its chain) covers."""
    active = _active_for_item(db, adj.rubric_item_id)
    versions = {v for a in active for v in a.from_version_ids}
    covered = [v for v in versions if str(adj.id) in chain(active, v)[1]]
    ids = [uuid.UUID(v) for v in covered] or [uuid.uuid4()]
    from_forms = (
        select(WrittenAttempt.id.label("attempt_id"))
        .join(WrittenFormItem, WrittenFormItem.form_id == WrittenAttempt.form_id)
        .where(WrittenFormItem.rubric_version_id.in_(ids), WrittenAttempt.status.in_(("active", "sealed")))
    )
    from_targets = select(RubricTarget.attempt_id.label("attempt_id")).where(RubricTarget.rubric_version_id.in_(ids))
    return from_forms.union(from_targets)


def preview(db: Session, adj: RubricAdjudication) -> dict[str, Any]:
    """Impact before and during the run: affected forms, attempts, released results, rescans and planned outcomes."""
    from portal_api.modules.written import rescans, review

    cand = list(db.scalars(_candidate_attempts(db, adj)))
    forms: set[uuid.UUID] = set()
    outcomes: dict[str, int] = {}
    released = revisions = attempts = 0
    for attempt_id in cand:
        attempt = db.get(WrittenAttempt, attempt_id)
        assert attempt is not None
        affected = _affected(db, adj, attempt)
        if not affected:
            continue
        attempts += 1
        forms.add(attempt.form_id)
        current = review.released_result(db, attempt.id)
        released += current is not None
        revisions += len(rescans.revisions_for(db, attempt.id, set(affected)))
        for pos, (old, new, _) in affected.items():
            kind = _planned(db, current, pos, old, new)
            outcomes[kind] = outcomes.get(kind, 0) + 1
    done = db.scalar(
        select(func.count())
        .select_from(RubricRegrade)
        .where(RubricRegrade.adjudication_id == adj.id, RubricRegrade.status == "done")
    )
    return {
        "forms": len(forms),
        "attempts": attempts,
        "released_results": released,
        "evidence_revisions": revisions,
        "question_outcomes": outcomes,
        "processed_attempts": int(done or 0),
    }


def _planned(db: Session, current: Any, pos: int, old: str, new: str) -> str:
    from portal_api.modules.written import review

    if current is None:
        return "retargeted"
    if review._status_of(current, str(pos)) != "scored":
        return "retargeted"
    a = db.get(ContentVersion, uuid.UUID(old))
    b = db.get(ContentVersion, uuid.UUID(new))
    assert a is not None and b is not None
    return "carried" if compatibility(a.body, b.body)["carry_forward"] else "review"


# ------------------------------------------------------------------ the regrade job
def run(db: Session, adjudication_id: uuid.UUID, limit: int = 50) -> dict[str, Any]:
    """Process up to ``limit`` affected attempts, one short transaction each. Safe to re-run and to run concurrently:
    the per-attempt row lock serialises work and the per-adjudication checkpoint row makes it idempotent."""
    adj = db.get(RubricAdjudication, adjudication_id)
    if adj is None:
        raise NotFound("Correction not found.")
    if adj.status != "active":
        return {"processed": 0, "remaining": 0, "superseded": True}
    finished = select(RubricRegrade.attempt_id).where(
        RubricRegrade.adjudication_id == adj.id, RubricRegrade.status == "done"
    )
    cand = _candidate_attempts(db, adj).subquery()
    todo = list(
        db.scalars(
            select(cand.c[0]).where(cand.c[0].not_in(finished)).order_by(cand.c[0]).limit(max(1, min(limit, 500)))
        )
    )
    db.rollback()  # no snapshot or lock carried into the per-attempt transactions
    summary: dict[str, int] = {}
    for attempt_id in todo:
        outcome = _regrade_attempt(db, adj.id, attempt_id)
        summary[outcome] = summary.get(outcome, 0) + 1
    remaining = db.scalar(
        select(func.count()).select_from(select(cand.c[0]).where(cand.c[0].not_in(finished)).subquery())
    )
    db.rollback()
    return {"processed": len(todo), "outcomes": summary, "remaining": int(remaining or 0), "superseded": False}


def _regrade_attempt(db: Session, adjudication_id: uuid.UUID, attempt_id: uuid.UUID) -> str:
    from portal_api.modules.written import review

    attempt = db.scalar(
        select(WrittenAttempt)
        .where(WrittenAttempt.id == attempt_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    adj = db.get(RubricAdjudication, adjudication_id, populate_existing=True)
    assert attempt is not None and adj is not None
    if adj.status != "active":
        db.rollback()
        return "superseded"
    existing = db.scalar(
        select(RubricRegrade).where(RubricRegrade.adjudication_id == adj.id, RubricRegrade.attempt_id == attempt.id)
    )
    if existing is not None and existing.status == "done":
        db.rollback()
        return "already_done"
    now = review._now(db)
    affected = _affected(db, adj, attempt)
    open_cases = list(
        db.scalars(
            select(review.WrittenReviewCase)
            .where(review.WrittenReviewCase.attempt_id == attempt.id, review.WrittenReviewCase.status == "queued")
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )
    current = review.released_result(db, attempt.id)
    outcomes: dict[str, str] = {}
    carried: dict[str, Any] = {}
    review_positions: list[int] = []
    for pos, (old, new, applied) in sorted(affected.items()):
        db.execute(
            insert(RubricTarget)
            .values(attempt_id=attempt.id, position=pos, rubric_version_id=uuid.UUID(new), adjudication_ids=applied)
            .on_conflict_do_update(
                index_elements=["attempt_id", "position"],
                set_={"rubric_version_id": uuid.UUID(new), "adjudication_ids": applied, "updated_at": now},
            )
        )
        kind = _planned(db, current, pos, old, new)
        covering = [c for c in open_cases if _covers(db, c, pos)]
        if covering:
            for c in covering:
                c.version += 1  # an in-flight lease on it must reload and mark under the corrected rubric
            if kind == "review":
                kind = "review_in_open_case"
        outcomes[str(pos)] = kind
        if kind == "carried":
            carried[str(pos)] = {"from_rubric": old, "to_rubric": new, "chain": applied}
        elif kind == "review":
            review_positions.append(pos)
    if not affected:
        outcomes = {}
    sv = None
    if carried and current is not None:
        sv = _publish_carry_forward(db, adj, attempt, current, carried, now)
    case = None
    if review_positions:
        case = _open_regrade_case(db, adj, attempt, review_positions, now)
    if affected:
        _notice(db, adj, attempt, outcomes)
    record(
        db,
        actor=None,
        action="written.rubric_regraded",
        target_type="written_attempt",
        target_id=str(attempt.id),
        details={"adjudication": str(adj.id), "outcomes": outcomes, "version": sv.version if sv else None},
    )
    row = existing or RubricRegrade(adjudication_id=adj.id, attempt_id=attempt.id)
    row.status = "done"
    row.outcomes = outcomes
    row.score_version_id = sv.id if sv else None
    row.case_id = case.id if case else None
    if existing is None:
        db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # a concurrent run finished this attempt first; its result stands
        return "already_done"
    return "regraded" if affected else "unaffected"


def _covers(db: Session, case: Any, pos: int) -> bool:
    """Whether an open case will (re-)mark this question: the whole script for an initial case, its positions for
    completion and regrade cases, and the requested (or widened) questions for a recheck."""
    from portal_api.modules.written import review

    if case.case_kind == "initial":
        return True
    if case.case_kind == "recheck":
        req = review.recheck_request(db, case)
        return req is not None and pos in {*req.positions, *req.expanded_positions}
    return pos in (case.positions or [])


def _publish_carry_forward(
    db: Session, adj: RubricAdjudication, attempt: WrittenAttempt, current: Any, carried: dict[str, Any], now: datetime
) -> Any:
    """A new released version identical in marks, re-based onto the corrected rubric. SYSTEM, never TEACHER: the
    human decisions are carried with their compatibility evidence, not re-reviewed."""
    from portal_api.modules.written import review

    anchor = _case(db, attempt, "released", sorted(int(p) for p in carried), adj, now)
    prior = review.latest(db, attempt.id)
    sv = review.WrittenScoreVersion(
        attempt_id=attempt.id,
        case_id=anchor.id,
        version=(prior.version + 1) if prior else 1,
        prior_version_id=prior.id if prior else None,
        decision_method="SYSTEM",
        case_kind="regrade",
        assessor_id=None,
        receipt_id=current.receipt_id,
        rubric_version_ids={**current.rubric_version_ids, **{p: c["to_rubric"] for p, c in carried.items()}},
        awards=current.awards,
        question_units=current.question_units,
        question_status=current.question_status,
        evidence_revisions=current.evidence_revisions,
        completeness=current.completeness,
        scored_max_units=current.scored_max_units,
        total_units=current.total_units,
        max_units=current.max_units,
        released=True,
        reason=f"Rubric correction applied; marks carried forward unchanged (scoring basis identical): {adj.reason}"[
            :1000
        ],
        regrade_detail={
            "adjudication": str(adj.id),
            "carried": {p: {**c, "from_version": current.version} for p, c in carried.items()},
            "compatibility": "scoring_basis_identical",
        },
    )
    db.add(sv)
    db.flush()
    return sv


def _open_regrade_case(
    db: Session, adj: RubricAdjudication, attempt: WrittenAttempt, positions: list[int], now: datetime
) -> Any:
    return _case(db, attempt, "queued", positions, adj, now)


def _case(
    db: Session, attempt: WrittenAttempt, status: str, positions: list[int], adj: RubricAdjudication, now: datetime
) -> Any:
    from portal_api.modules.written import review

    form = db.get(WrittenForm, attempt.form_id)
    assert form is not None
    seq = db.scalar(
        select(func.max(review.WrittenReviewCase.opened_seq)).where(
            review.WrittenReviewCase.attempt_id == attempt.id, review.WrittenReviewCase.case_kind == "regrade"
        )
    )
    case = review.WrittenReviewCase(
        attempt_id=attempt.id,
        case_kind="regrade",
        opened_seq=(seq or 0) + 1,
        grade_number=form.grade_number,
        subject_code=form.subject_code,
        status=status,
        positions=positions,
        reason=f"Rubric correction: {adj.reason}"[:1000],
        due_at=now + review.REVIEW_DUE,
        released_at=now if status == "released" else None,
        adjudication_id=adj.id,
    )
    db.add(case)
    db.flush()
    return case


def _qs(ps: list[int]) -> str:
    return ", ".join(str(p) for p in sorted(ps))


def _notice(db: Session, adj: RubricAdjudication, attempt: WrittenAttempt, outcomes: dict[str, str]) -> None:
    by_kind: dict[str, list[int]] = {}
    for p, k in outcomes.items():
        by_kind.setdefault(k, []).append(int(p))
    parts = []
    if by_kind.get("carried"):
        parts.append(f"Your marks for question {_qs(by_kind['carried'])} are unchanged.")
    if by_kind.get("review") or by_kind.get("review_in_open_case"):
        parts.append(
            f"A teacher will re-mark question {_qs(by_kind.get('review', []) + by_kind.get('review_in_open_case', []))}"
            " under the corrected guide; your current marks stay until then."
        )
    if by_kind.get("retargeted"):
        parts.append(f"Question {_qs(by_kind['retargeted'])} will be marked with the corrected guide.")
    db.execute(
        insert(WrittenNotice)
        .values(
            attempt_id=attempt.id,
            user_id=attempt.user_id,
            cause_id=adj.id,
            kind="rubric_correction",
            positions=sorted(int(p) for p in outcomes),
            message=("An academic reviewer corrected the marking guide. " + " ".join(parts))[:2000],
        )
        .on_conflict_do_nothing(index_elements=["attempt_id", "cause_id", "kind"])
    )


def notices(db: Session, attempt_id: uuid.UUID) -> list[WrittenNotice]:
    return list(
        db.scalars(
            select(WrittenNotice).where(WrittenNotice.attempt_id == attempt_id).order_by(WrittenNotice.created_at)
        )
    )
