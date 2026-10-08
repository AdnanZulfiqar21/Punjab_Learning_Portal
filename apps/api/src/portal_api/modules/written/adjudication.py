"""Rubric adjudications across attempts (W06.S2.T3; §20.10; WA-AC26/64/77/78; PR #34 review W06-01..W06-09).

A rubric correction is first made through the editorial workflow: a new rubric version is drafted, reviewed and
published, and from then on new forms use it. Applying it to work already submitted is a separate, historical decision:
an academic adjudicator with an MFA session records a :class:`RubricAdjudication` naming the superseded rubric versions
it corrects, the corrected (currently published) version and a reason. It never edits evidence, an earlier score
version or the original form; it changes which rubric is the *effective marking basis* for affected questions.

Pinned basis (W06-02). Only **sealed** attempts are regraded. An attempt still being written keeps the rubric it was
started with; once sealed it becomes eligible, and sealing queues the correction for it. Marking a sealed script whose
effective basis has moved but hasn't been applied yet is refused (``CORRECTION_PENDING``) rather than silently done on
either rubric.

Effective set. Corrections chain (A -> B, then B -> C). The effective rubric of a question is computed from the
attempt's *pinned* rubric through the active corrections, so superseding a correction re-targets attempts the old one
had already moved. Cycles and over-long chains are explicit errors (``ChainError``). Every released score version stores
the correction chain behind each question and a hash of it (W06-03); later corrections never change that record.

Compatible denominators. A rubric correction must keep every slot's maximum. A different total is a question change.

Regrade per attempt (bounded, resumable, idempotent; run by the durable worker in ``regrade_jobs``): one short
transaction per attempt that takes the same per-rubric lock as creation (so a supersede can't interleave) and then the
attempt row. Outcomes per affected question:

* scored, scoring basis identical (criteria, maxima, levels, groups, dependencies, descriptions; only reviewer notes
  differ): the human marks carry forward onto the corrected rubric in a SYSTEM/regrade version with evidence;
* scored, scoring basis changed: a teacher re-marks it in a ``regrade`` case (never the adjudicator who approved the
  correction); the released result stays until then. An open case already covering it is re-targeted instead;
* pending, unavailable or not yet marked: the corrected rubric becomes the target for later marking.

Every affected learner gets one notice per correction. Nothing here consumes or releases allowance.
"""

from __future__ import annotations

import hashlib
import json
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
    text,
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
from portal_api.modules.written.models import WrittenAttempt, WrittenForm

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
# Integrity conflicts that mean "another run already did this attempt" (W06-04); anything else is a real failure.
IDEMPOTENT_CONSTRAINTS = frozenset({"uq_written_regrade", "uq_written_regrade_version"})


class ChainError(Exception):
    """A correction chain that cycles or exceeds MAX_CHAIN: an operator error, never silently truncated."""


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
    supersedes_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("written_rubric_adjudication.id", ondelete="RESTRICT")
    )
    approved_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RubricRegrade(Base):
    """Checkpoint and outcome of one correction for one attempt. ``failed`` rows wait for an explicit retry."""

    __tablename__ = "written_rubric_regrade"
    __table_args__ = (
        UniqueConstraint("adjudication_id", "attempt_id", name="uq_written_regrade"),
        CheckConstraint("status in ('done','failed')", name="written_regrade_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    adjudication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("written_rubric_adjudication.id", ondelete="RESTRICT"), index=True
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_attempt.id", ondelete="RESTRICT"))
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(10), default="done")
    outcomes: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict)  # position -> carried|review|...
    error: Mapped[str | None] = mapped_column(Text)
    score_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("written_score_version.id", ondelete="RESTRICT")
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("written_review_case.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RubricTarget(Base):
    """The rubric marking now uses for one question of one attempt (absent: the form's pinned rubric)."""

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
def _perms(db: Session, who: Principal, grade: int, subject: str) -> frozenset[Permission]:
    return frozenset(permissions_for(roles_in_scope(db, who.user.id, grade, subject)))


def require_adjudicator(db: Session, who: Principal, grade: int, subject: str) -> None:
    """W06-01: the adjudicate permission in this class and subject, with an MFA session (checked here as well as by
    the route dependency, so no caller can reach a mutation without both)."""
    if Permission.adjudicate not in _perms(db, who, grade, subject):
        raise Forbidden("Only an academic adjudicator for this class and subject can apply a rubric correction.")
    if not who.claims.mfa:
        raise Forbidden("This action needs a multi-factor authenticated session. Sign in again with MFA.")


def _may_read(db: Session, who: Principal, grade: int, subject: str) -> bool:
    return bool({Permission.adjudicate, Permission.review_content} & _perms(db, who, grade, subject))


def lock_rubric(db: Session, rubric_item_id: uuid.UUID) -> None:
    """Per-rubric lock shared by creation/supersession and every regrade transaction (W06-05). Taken first."""
    db.execute(select(func.pg_advisory_xact_lock(rubric_item_id.int & 0x7FFFFFFFFFFFFFFF)))


# ------------------------------------------------------------------ effective chain
def chain(active: list[RubricAdjudication], version_id: str) -> tuple[str, list[str]]:
    """Follow the active corrections from a rubric version to its effective version (the complete approved set)."""
    applied: list[str] = []
    seen = {version_id}
    current = version_id
    while True:
        nxt = next((a for a in active if current in a.from_version_ids), None)
        if nxt is None:
            return current, applied
        if len(applied) >= MAX_CHAIN:
            raise ChainError(f"Correction chain from {version_id} is longer than {MAX_CHAIN} steps.")
        applied.append(str(nxt.id))
        current = str(nxt.to_version_id)
        if current in seen:
            raise ChainError(f"Correction chain from {version_id} returns to {current} (a cycle).")
        seen.add(current)


def _active_for_items(db: Session, item_ids: set[uuid.UUID]) -> dict[uuid.UUID, list[RubricAdjudication]]:
    out: dict[uuid.UUID, list[RubricAdjudication]] = {i: [] for i in item_ids}
    if item_ids:
        for a in db.scalars(
            select(RubricAdjudication).where(
                RubricAdjudication.rubric_item_id.in_(item_ids), RubricAdjudication.status == "active"
            )
        ):
            out[a.rubric_item_id].append(a)
    return out


def effective(db: Session, attempt: WrittenAttempt) -> dict[int, tuple[str, str, list[str]]]:
    """Per question: (pinned rubric, effective rubric, corrections applied), always from the pinned basis."""
    form = db.get(WrittenForm, attempt.form_id)
    assert form is not None
    pinned = {fi.position: fi.rubric_version_id for fi in form.items}
    items = dict(
        db.execute(
            select(ContentVersion.id, ContentVersion.item_id).where(ContentVersion.id.in_(pinned.values()))
        ).all()
    )
    active = _active_for_items(db, set(items.values()))
    out = {}
    for pos, vid in pinned.items():
        target, applied = chain(active[items[vid]], str(vid))
        out[pos] = (str(vid), target, applied)
    return out


def targets(db: Session, attempt_id: uuid.UUID) -> dict[int, uuid.UUID]:
    """The rubric marking uses now for each re-targeted question (marking and results read this)."""
    return {
        t.position: t.rubric_version_id
        for t in db.scalars(select(RubricTarget).where(RubricTarget.attempt_id == attempt_id))
    }


def provenance_hash(eff: dict[str, list[str]]) -> str:
    return hashlib.sha256(json.dumps(eff, sort_keys=True).encode()).hexdigest()


def basis_for_decision(
    db: Session, attempt: WrittenAttempt, rubric_by_position: dict[str, str], positions: set[str]
) -> dict[str, list[str]]:
    """W06-03: the authorised correction chain behind each question a decision marks, derived from the pinned basis
    and the active corrections (not from mutable state). A decision whose rubric isn't the current effective one is
    refused: the correction must be applied to this script first."""
    eff = effective(db, attempt)
    out: dict[str, list[str]] = {}
    stale = []
    for p in sorted(positions, key=int):
        _, target, applied = eff[int(p)]
        if rubric_by_position[p] != target:
            stale.append(int(p))
        out[p] = applied
    if stale:
        raise Conflict(
            "A rubric correction for these questions hasn't been applied to this script yet. It is queued; try again "
            "once it has run.",
            code_reason="CORRECTION_PENDING",
            positions=stale,
        )
    return out


# ------------------------------------------------------------------ creation
def sources(db: Session, who: Principal, rubric_item_id: uuid.UUID) -> dict[str, Any]:
    """What a correction of this rubric could apply to (W06-07): earlier published versions for the same question
    with their computed compatibility and denominator check, the active corrections claiming them, and how many
    submitted scripts were started on each. Bounded: a fixed number of queries."""
    item = db.get(ContentItem, rubric_item_id)
    if item is None or item.kind != "rubric" or not _may_read(db, who, item.grade_number, item.subject_code):
        raise NotFound("Rubric not found.")
    to = db.get(ContentVersion, item.published_version_id) if item.published_version_id else None
    if to is None:
        return {"published_version_id": None, "published_number": None, "versions": [], "active": []}
    qv = str(to.body.get("question_version_id"))
    versions = [
        v
        for v in db.scalars(
            select(ContentVersion)
            .where(ContentVersion.item_id == item.id, ContentVersion.status == VersionStatus.superseded.value)
            .order_by(ContentVersion.number)
        )
        if str(v.body.get("question_version_id")) == qv
    ]
    active = list(
        db.scalars(
            select(RubricAdjudication).where(
                RubricAdjudication.rubric_item_id == item.id, RubricAdjudication.status == "active"
            )
        )
    )
    counts: dict[str, int] = dict(
        db.execute(
            text(
                "select fi.rubric_version_id::text, count(distinct a.id) from written_form_item fi "
                "join written_attempt a on a.form_id = fi.form_id and a.status = 'sealed' "
                "where fi.rubric_version_id = any(cast(:ids as uuid[])) group by 1"
            ),
            {"ids": [str(v.id) for v in versions]},
        ).all()
    )
    return {
        "published_version_id": str(to.id),
        "published_number": to.number,
        "versions": [
            {
                "id": str(v.id),
                "number": v.number,
                "denominator_compatible": _slot_totals(v.body) == _slot_totals(to.body),
                "compatibility": compatibility(v.body, to.body),
                "claimed_by": [str(a.id) for a in active if str(v.id) in a.from_version_ids],
                "submitted_scripts": int(counts.get(str(v.id), 0)),
            }
            for v in versions
        ],
        "active": [
            {"id": str(a.id), "from_version_ids": a.from_version_ids, "to_version_id": str(a.to_version_id)}
            for a in active
        ],
    }


def create(
    db: Session,
    who: Principal,
    *,
    rubric_item_id: uuid.UUID,
    reason: str,
    from_version_ids: list[uuid.UUID] | None = None,
    supersedes_ids: list[uuid.UUID] | None = None,
) -> RubricAdjudication:
    item = db.get(ContentItem, rubric_item_id)
    if item is None or item.kind != "rubric":
        raise NotFound("Rubric not found.")
    require_adjudicator(db, who, item.grade_number, item.subject_code)
    if len(reason.strip()) < 20:
        raise Unprocessable("Explain the correction and why it applies to work already marked (20+ characters).")
    if item.availability != Availability.live.value or item.published_version_id is None:
        raise Unprocessable("Publish the corrected rubric first; only a live, published rubric can be applied.")
    # Serialised with every other creation and every regrade transaction for this rubric (W06-05).
    lock_rubric(db, item.id)
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
    chosen = sorted({str(v) for v in from_version_ids}) if from_version_ids else sorted(candidates)
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
    active = list(
        db.scalars(
            select(RubricAdjudication)
            .where(RubricAdjudication.rubric_item_id == item.id, RubricAdjudication.status == "active")
            .with_for_update()
        )
    )
    overlapping = {a.id for a in active if set(a.from_version_ids) & set(chosen)}
    named = set(supersedes_ids or [])
    if overlapping != named:
        if overlapping - named:
            raise Conflict(
                "Active corrections already cover some of these versions; name each one you replace.",
                code_reason="SUPERSEDE_REQUIRED",
                active=sorted(str(a) for a in overlapping),
            )
        raise Unprocessable(
            "Only an active correction for these versions can be replaced.",
            code_reason="NOT_SUPERSEDABLE",
            errors=sorted(str(a) for a in named - overlapping),
        )
    adj = RubricAdjudication(
        id=uuid.uuid4(),
        rubric_item_id=item.id,
        grade_number=item.grade_number,
        subject_code=item.subject_code,
        from_version_ids=chosen,
        to_version_id=to.id,
        reason=reason.strip()[:2000],
        compatibility=compat,
        supersedes_ids=sorted(str(a) for a in overlapping),
        approved_by=who.user.id,
    )
    remaining = [a for a in active if a.id not in overlapping] + [adj]
    try:
        for a in remaining:  # the resulting active set must still form proper chains
            for v in a.from_version_ids:
                chain(remaining, v)
    except ChainError as e:
        raise Unprocessable(str(e), code_reason="CHAIN_INVALID") from None
    db.add(adj)
    db.flush()
    for a in active:
        if a.id in overlapping:
            a.status = "superseded"
            a.superseded_by_id = adj.id
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
            "supersedes": adj.supersedes_ids,
            "carry_forward": {v: c["carry_forward"] for v, c in compat.items()},
        },
    )
    db.commit()
    db.refresh(adj)
    return adj


def get(db: Session, who: Principal, adjudication_id: uuid.UUID) -> RubricAdjudication:
    adj = db.get(RubricAdjudication, adjudication_id)
    if adj is None or not _may_read(db, who, adj.grade_number, adj.subject_code):
        raise NotFound("Correction not found.")
    return adj


def visible(db: Session, who: Principal) -> list[RubricAdjudication]:
    rows = db.scalars(select(RubricAdjudication).order_by(RubricAdjudication.approved_at.desc()).limit(200))
    return [a for a in rows if _may_read(db, who, a.grade_number, a.subject_code)]


# ------------------------------------------------------------------ impact (bounded; W06-08/09)
def _covered_versions(db: Session, adj: RubricAdjudication) -> list[str]:
    """Pinned rubric versions whose effective chain passes through ``adj``."""
    every = list(db.scalars(select(RubricAdjudication).where(RubricAdjudication.rubric_item_id == adj.rubric_item_id)))
    active = [a for a in every if a.status == "active"]
    versions = {v for a in every for v in a.from_version_ids}
    if adj.status != "active":
        return []
    return sorted(v for v in versions if str(adj.id) in chain(active, v)[1])


_CANDIDATES = (
    "select distinct a.id as attempt_id, a.form_id from written_attempt a "
    "join written_form_item fi on fi.form_id = a.form_id "
    "where a.status = 'sealed' and fi.rubric_version_id = any(cast(:versions as uuid[]))"
)


def preview(db: Session, adj: RubricAdjudication) -> dict[str, Any]:
    """Totals in a fixed number of aggregate queries, whatever the size of history: affected submitted scripts,
    processed, remaining and failed, plus what was applied so far."""
    versions = _covered_versions(db, adj)
    row = db.execute(
        text(
            f"with c as ({_CANDIDATES}) select "  # noqa: S608 - fixed SQL; values are bound parameters
            "(select count(*) from c) as total, (select count(distinct form_id) from c) as forms, "
            "(select count(*) from c where exists (select 1 from written_score_version s "
            " where s.attempt_id = c.attempt_id and s.released)) as released, "
            "(select count(*) from written_evidence_revision r join c on c.attempt_id = r.attempt_id) as revisions, "
            "(select count(*) from written_rubric_regrade g join c on c.attempt_id = g.attempt_id "
            " where g.adjudication_id = :adj and g.status = 'done') as processed, "
            "(select count(*) from written_rubric_regrade g join c on c.attempt_id = g.attempt_id "
            " where g.adjudication_id = :adj and g.status = 'failed') as failed"
        ),
        {"versions": versions, "adj": str(adj.id)},
    ).one()
    applied: dict[str, int] = dict(
        db.execute(
            text(
                "select o.value, count(*) from written_rubric_regrade g, jsonb_each_text(g.outcomes) o "
                "where g.adjudication_id = :adj and g.status = 'done' group by 1"
            ),
            {"adj": str(adj.id)},
        ).all()
    )
    unaffected = db.scalar(
        text(
            "select count(*) from written_rubric_regrade where adjudication_id = :adj and status = 'done' "
            "and outcomes = '{}'::jsonb"
        ),
        {"adj": str(adj.id)},
    )
    total, processed, failed = int(row.total), int(row.processed), int(row.failed)
    return {
        "total_attempts": total,
        "processed": processed,
        "failed": failed,
        "remaining": max(0, total - processed - failed),
        "unaffected": int(unaffected or 0),
        "forms": int(row.forms),
        "released_results": int(row.released),
        "evidence_revisions": int(row.revisions),
        "applied_outcomes": {k: int(v) for k, v in applied.items()},
    }


def attempts_page(db: Session, adj: RubricAdjudication, offset: int, limit: int) -> dict[str, Any]:
    """Paginated drill-down of processed scripts (reference only; no learner identity)."""
    total = db.scalar(select(func.count()).select_from(RubricRegrade).where(RubricRegrade.adjudication_id == adj.id))
    rows = db.scalars(
        select(RubricRegrade)
        .where(RubricRegrade.adjudication_id == adj.id)
        .order_by(RubricRegrade.created_at, RubricRegrade.id)
        .offset(offset)
        .limit(limit)
    )
    return {
        "total": int(total or 0),
        "items": [
            {
                "reference": str(r.attempt_id)[:8],
                "status": r.status,
                "outcomes": r.outcomes,
                "error": r.error,
                "at": r.created_at,
            }
            for r in rows
        ],
    }


# ------------------------------------------------------------------ regrade
def _candidates(db: Session, adj: RubricAdjudication, limit: int) -> list[uuid.UUID]:
    """Submitted scripts on a covered version without a done or failed row for this correction."""
    versions = _covered_versions(db, adj)
    return list(
        db.execute(
            text(
                f"select c.attempt_id from ({_CANDIDATES}) c "  # noqa: S608 - fixed SQL; values are bound
                "where not exists (select 1 from written_rubric_regrade g where g.adjudication_id = :adj "
                "and g.attempt_id = c.attempt_id) order by c.attempt_id limit :limit"
            ),
            {"versions": versions, "adj": str(adj.id), "limit": limit},
        ).scalars()
    )


def _remaining(db: Session, adj: RubricAdjudication) -> int:
    n = db.scalar(
        text(
            f"select count(*) from ({_CANDIDATES}) c where not exists (select 1 from written_rubric_regrade g "  # noqa: S608
            "where g.adjudication_id = :adj and g.attempt_id = c.attempt_id)"
        ),
        {"versions": _covered_versions(db, adj), "adj": str(adj.id)},
    )
    return int(n or 0)


def process_batch(
    db: Session, adjudication_id: uuid.UUID, limit: int = 50, job_id: uuid.UUID | None = None
) -> dict[str, Any]:
    """Process up to ``limit`` affected scripts, one short transaction each. An attempt that fails is recorded as
    failed (with its error) and skipped until an explicit retry; it is never reported as done."""
    adj = db.get(RubricAdjudication, adjudication_id)
    if adj is None:
        raise NotFound("Correction not found.")
    counts: dict[str, Any] = {
        "processed": 0,
        "regraded": 0,
        "unaffected": 0,
        "failed": 0,
        "superseded": adj.status != "active",
    }
    if adj.status != "active":
        db.rollback()
        return {**counts, "remaining": 0, "last_error": None}
    todo = _candidates(db, adj, max(1, min(limit, 500)))
    db.rollback()  # no snapshot or lock carried into the per-attempt transactions
    last_error = None
    for attempt_id in todo:
        try:
            outcome = _regrade_attempt(db, adjudication_id, attempt_id, job_id)
        except Exception as e:
            db.rollback()
            last_error = f"{type(e).__name__}: {str(e).splitlines()[0][:300]}"
            _record_failure(db, adjudication_id, attempt_id, job_id, last_error)
            counts["failed"] += 1
            continue
        if outcome == "superseded":
            counts["superseded"] = True
            break
        counts["processed"] += 1
        if outcome == "regraded":
            counts["regraded"] += 1
        elif outcome == "unaffected":
            counts["unaffected"] += 1
    adj = db.get(RubricAdjudication, adjudication_id, populate_existing=True)
    assert adj is not None
    remaining = 0 if adj.status != "active" else _remaining(db, adj)
    db.rollback()
    return {**counts, "remaining": remaining, "last_error": last_error}


def _record_failure(
    db: Session, adjudication_id: uuid.UUID, attempt_id: uuid.UUID, job_id: uuid.UUID | None, error: str
) -> None:
    db.execute(
        insert(RubricRegrade)
        .values(
            id=uuid.uuid4(),
            adjudication_id=adjudication_id,
            attempt_id=attempt_id,
            job_id=job_id,
            status="failed",
            outcomes={},
            error=error,
        )
        .on_conflict_do_update(constraint="uq_written_regrade", set_={"status": "failed", "error": error})
    )
    record(
        db,
        actor=None,
        action="written.rubric_regrade_failed",
        target_type="written_attempt",
        target_id=str(attempt_id),
        details={"adjudication": str(adjudication_id), "job": str(job_id) if job_id else None, "error": error},
    )
    db.commit()


def _constraint(e: IntegrityError) -> str | None:
    return getattr(getattr(e.orig, "diag", None), "constraint_name", None)


def _regrade_attempt(
    db: Session, adjudication_id: uuid.UUID, attempt_id: uuid.UUID, job_id: uuid.UUID | None = None
) -> str:
    from portal_api.modules.written import review

    item_id = db.scalar(select(RubricAdjudication.rubric_item_id).where(RubricAdjudication.id == adjudication_id))
    assert item_id is not None
    lock_rubric(db, item_id)  # same lock, same order as creation: a supersede can't interleave (W06-05)
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
    if attempt.status != "sealed":
        db.rollback()
        return "skipped"  # work in progress keeps its pinned basis (W06-02)
    existing = db.scalar(
        select(RubricRegrade).where(RubricRegrade.adjudication_id == adj.id, RubricRegrade.attempt_id == attempt.id)
    )
    if existing is not None and existing.status == "done":
        db.rollback()
        return "already_done"
    now = review._now(db)
    eff = effective(db, attempt)
    over = targets(db, attempt.id)
    affected = {
        pos: (str(over.get(pos, pinned)), target, applied)
        for pos, (pinned, target, applied) in eff.items()
        if str(adj.id) in applied and str(over.get(pos, pinned)) != target
    }
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
    sv = None
    if carried and current is not None:
        sv = _publish_carry_forward(db, adj, attempt, current, carried, now)
    case = None
    if review_positions:
        case = _case(db, attempt, "queued", review_positions, adj, now)
    if affected:
        _notice(db, adj, attempt, outcomes)
    record(
        db,
        actor=None,
        action="written.rubric_regraded",
        target_type="written_attempt",
        target_id=str(attempt.id),
        details={
            "adjudication": str(adj.id),
            "job": str(job_id) if job_id else None,
            "approved_by": str(adj.approved_by),
            "outcomes": outcomes,
            "version": sv.version if sv else None,
        },
    )
    row = existing or RubricRegrade(adjudication_id=adj.id, attempt_id=attempt.id)
    row.status = "done"
    row.error = None
    row.job_id = job_id
    row.outcomes = outcomes
    row.score_version_id = sv.id if sv else None
    row.case_id = case.id if case else None
    if existing is None:
        db.add(row)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if _constraint(e) in IDEMPOTENT_CONSTRAINTS:
            return "already_done"  # a concurrent run finished this attempt first; its result stands
        raise  # anything else is a real failure (W06-04)
    return "regraded" if affected else "unaffected"


def _planned(db: Session, current: Any, pos: int, old: str, new: str) -> str:
    from portal_api.modules.written import review

    if current is None or review._status_of(current, str(pos)) != "scored":
        return "retargeted"
    a = db.get(ContentVersion, uuid.UUID(old))
    b = db.get(ContentVersion, uuid.UUID(new))
    assert a is not None and b is not None
    return "carried" if compatibility(a.body, b.body)["carry_forward"] else "review"


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
    eff = {**(current.effective_adjudication or {}), **{p: c["chain"] for p, c in carried.items()}}
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
        effective_adjudication=eff,
        adjudication_hash=provenance_hash(eff),
    )
    db.add(sv)
    db.flush()
    return sv


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


def corrections_for_sealed(db: Session, attempt: WrittenAttempt) -> list[RubricAdjudication]:
    """Active corrections that move this just-sealed script's basis (W06-02): sealing queues them for it."""
    ids = {aid for _, target_, applied in effective(db, attempt).values() for aid in applied if target_}
    if not ids:
        return []
    return list(db.scalars(select(RubricAdjudication).where(RubricAdjudication.id.in_([uuid.UUID(i) for i in ids]))))
