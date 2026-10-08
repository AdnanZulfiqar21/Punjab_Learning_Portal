"""Teacher marking of sealed written scripts (W06.S1, §20.10).

Every sealed script gets one initial review case. Reviewers act only inside their grade/subject scope, take a time-
limited lease, and submit decisions with the case's expected version (compare-and-swap): two teachers can't silently
overwrite each other, and a stale decision gets an explicit version error. Each decision creates a new immutable
WrittenScoreVersion (actual assessor, case kind, rubric versions, evidence epoch, per-criterion awards and reasons,
prior version). Learners see a result only once a teacher releases it. No automatic marking exists (B10).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base
from portal_api.errors import Conflict, Forbidden, NotFound, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.content import written as wq
from portal_api.modules.content.models import ContentVersion
from portal_api.modules.content.workflow import roles_in_scope
from portal_api.modules.identity.deps import Principal
from portal_api.modules.identity.permissions import Permission, permissions_for
from portal_api.modules.written import storage
from portal_api.modules.written.models import WrittenAttempt, WrittenForm, WrittenPage, WrittenReceipt

LEASE = timedelta(minutes=20)
REVIEW_DUE = timedelta(hours=48)  # §20.10 proposed staffed target (99% within 48 h); a service obligation, not a mark
QUESTION_STATUSES = ("scored", "pending", "unavailable")


class WrittenReviewCase(Base):
    __tablename__ = "written_review_case"
    __table_args__ = (
        UniqueConstraint("attempt_id", "case_kind", "opened_seq", name="uq_written_case"),
        CheckConstraint("status in ('queued','released')", name="written_case_status"),
        CheckConstraint("case_kind in ('initial','recheck','completion')", name="written_case_kind"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_attempt.id", ondelete="RESTRICT"), index=True)
    case_kind: Mapped[str] = mapped_column(String(10), default="initial")
    opened_seq: Mapped[int] = mapped_column(SmallInteger, default=1)
    grade_number: Mapped[int] = mapped_column(SmallInteger)
    subject_code: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(10), default="queued")
    version: Mapped[int] = mapped_column(Integer, default=0)  # expected-version CAS for decisions
    lease_holder: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)  # learner's recheck reason (recheck cases)
    positions: Mapped[list[int] | None] = mapped_column(JSONB)  # completion cases: the questions still pending
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # service obligation for accepted work
    # OCT8-03: the released version the marker saw when taking the lease; a later change to this case's questions
    # by another publication makes the decision a recoverable conflict instead of a silent overwrite.
    base_version: Mapped[int | None] = mapped_column(SmallInteger)
    predecessor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("written_review_case.id", ondelete="RESTRICT")
    )  # completion successor of a partially resolved completion case (OCT8-02)


class WrittenScoreVersion(Base):
    __tablename__ = "written_score_version"
    __table_args__ = (UniqueConstraint("attempt_id", "version"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_attempt.id", ondelete="RESTRICT"), index=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_review_case.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(SmallInteger)
    prior_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("written_score_version.id", ondelete="RESTRICT")
    )
    decision_method: Mapped[str] = mapped_column(String(10), default="TEACHER")
    case_kind: Mapped[str] = mapped_column(String(10))
    assessor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    receipt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("written_receipt.id", ondelete="RESTRICT")
    )  # evidence epoch
    rubric_version_ids: Mapped[dict[str, str]] = mapped_column(JSONB)  # position -> rubric version id
    awards: Mapped[dict[str, Any]] = mapped_column(JSONB)  # position -> criterion -> {units, reason}
    question_units: Mapped[dict[str, int]] = mapped_column(JSONB)  # position -> earned units (scored only)
    # R05: position -> {"status": scored|pending|unavailable, "reason": str}. Missing entries mean scored (pre-R05).
    question_status: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    completeness: Mapped[str] = mapped_column(String(20), default="complete", server_default="complete")
    scored_max_units: Mapped[int | None] = mapped_column(Integer)  # sum of maxima of scored questions
    total_units: Mapped[int] = mapped_column(Integer)
    max_units: Mapped[int] = mapped_column(Integer)
    released: Mapped[bool] = mapped_column(default=False)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewCapacity(Base):
    """Funded teacher-review capacity for one class and subject (review R05, §20.13.3). A reviewer role grant alone is
    not evidence that review is funded: new written starts are admitted only while queued cases are below this limit.
    Work already accepted (rechecks, completion cases) is never refused by it."""

    __tablename__ = "written_review_capacity"
    grade_number: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    subject_code: Mapped[str] = mapped_column(String(40), primary_key=True)
    max_open_cases: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WrittenRecheckRequest(Base):
    """A learner's recheck request, pinned structurally (RECHECK-01).

    It names the exact released score version it disputes and the questions (optionally criteria) in scope. One request
    per target version is enforced by the database, so duplicate or concurrent requests can't both open a case. A
    correction releases a new version, which a learner may appeal for the questions that correction changed.
    """

    __tablename__ = "written_recheck_request"
    __table_args__ = (
        UniqueConstraint("target_version_id", name="uq_recheck_target_version"),
        CheckConstraint("status in ('open','resolved')", name="written_recheck_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_attempt.id", ondelete="RESTRICT"), index=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_review_case.id", ondelete="RESTRICT"), unique=True)
    target_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_score_version.id", ondelete="RESTRICT"))
    positions: Mapped[list[int]] = mapped_column(JSONB)
    criteria: Mapped[dict[str, list[str]]] = mapped_column(JSONB, default=dict)  # position -> disputed criteria
    reason: Mapped[str] = mapped_column(Text)
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(10), default="open")
    expanded_positions: Mapped[list[int]] = mapped_column(JSONB, default=list)  # added by an adjudicator, with reason
    expansion_reason: Mapped[str | None] = mapped_column(Text)
    expanded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    resolved_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("written_score_version.id", ondelete="RESTRICT")
    )
    rebases: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default="[]")  # OCT8-03 audit
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _now(db: Session) -> datetime:
    now: datetime = db.execute(select(func.clock_timestamp())).scalar_one()
    return now


def open_initial_case(db: Session, attempt: WrittenAttempt) -> None:
    """Called inside the seal transaction: every sealed script enters the marking queue exactly once."""
    form = db.get(WrittenForm, attempt.form_id)
    assert form is not None
    db.add(
        WrittenReviewCase(
            attempt_id=attempt.id,
            case_kind="initial",
            opened_seq=1,
            grade_number=form.grade_number,
            subject_code=form.subject_code,
            due_at=_now(db) + REVIEW_DUE,
        )
    )


def open_cases(db: Session, grade: int, subject: str) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(WrittenReviewCase)
            .where(
                WrittenReviewCase.status == "queued",
                WrittenReviewCase.grade_number == grade,
                WrittenReviewCase.subject_code == subject,
            )
        )
        or 0
    )


def open_permits(db: Session, grade: int, subject: str) -> int:
    """Started, unsealed written attempts in this scope: each may become a case, so each counts as committed load."""
    return int(
        db.scalar(
            select(func.count())
            .select_from(WrittenAttempt)
            .join(WrittenForm, WrittenForm.id == WrittenAttempt.form_id)
            .where(
                WrittenAttempt.status == "active",
                WrittenForm.grade_number == grade,
                WrittenForm.subject_code == subject,
            )
        )
        or 0
    )


def lock_capacity(db: Session, grade: int, subject: str) -> None:
    """Serialize capacity admission for one class and subject until the transaction ends (different learners
    starting at the same moment must not both take the last place)."""
    import hashlib

    digest = hashlib.sha256(f"written-capacity:{grade}:{subject}".encode()).digest()
    key = int.from_bytes(digest[:8], "big", signed=True)
    db.execute(select(func.pg_advisory_xact_lock(key)))


def capacity_state(db: Session, grade: int, subject: str) -> dict[str, Any]:
    cap = db.get(ReviewCapacity, (grade, subject))
    n = open_cases(db, grade, subject)
    permits = open_permits(db, grade, subject)
    return {
        "configured": cap is not None and cap.max_open_cases > 0,
        "max_open_cases": cap.max_open_cases if cap else 0,
        "open_cases": n,
        "open_permits": permits,
        "accepting": cap is not None and n + permits < cap.max_open_cases,
    }


def set_capacity(db: Session, who: Principal, grade: int, subject: str, max_open_cases: int, reason: str) -> None:
    cap = db.get(ReviewCapacity, (grade, subject))
    if cap is None:
        cap = ReviewCapacity(grade_number=grade, subject_code=subject, max_open_cases=max_open_cases, reason=reason)
        db.add(cap)
    previous = cap.max_open_cases if cap.updated_at else None
    cap.max_open_cases = max_open_cases
    cap.reason = reason.strip()
    cap.updated_by = who.user.id
    cap.updated_at = _now(db)
    record(
        db,
        actor=who.user.id,
        action="written.capacity_set",
        target_type="review_capacity",
        target_id=f"{grade}:{subject}",
        details={"max_open_cases": max_open_cases, "previous": previous, "reason": reason.strip()},
    )
    db.commit()


def _can_review(db: Session, who: Principal, case: WrittenReviewCase) -> bool:
    return Permission.review_content in permissions_for(
        roles_in_scope(db, who.user.id, case.grade_number, case.subject_code)
    )


def can_adjudicate(db: Session, who: Principal, case: WrittenReviewCase) -> bool:
    return Permission.adjudicate in permissions_for(
        roles_in_scope(db, who.user.id, case.grade_number, case.subject_code)
    )


def _case(db: Session, who: Principal, case_id: uuid.UUID, *, lock: bool = False) -> WrittenReviewCase:
    stmt = select(WrittenReviewCase).where(WrittenReviewCase.id == case_id)
    if lock:
        stmt = stmt.with_for_update()
    case = db.scalar(stmt)
    if case is None or not _can_review(db, who, case):
        raise NotFound("Review case not found.")  # out-of-scope cases are invisible
    attempt = db.get(WrittenAttempt, case.attempt_id)
    if attempt is not None and attempt.user_id == who.user.id:
        raise Forbidden("You can't mark your own work.")
    return case


def get_case(db: Session, who: Principal, case_id: uuid.UUID) -> WrittenReviewCase:
    return _case(db, who, case_id)


def queue(db: Session, who: Principal, limit: int = 200) -> list[WrittenReviewCase]:
    """Queued cases in the reviewer's scope, oldest first. Scope is applied in SQL before the limit."""
    from sqlalchemy import and_, false, or_, true

    from portal_api.modules.identity.models import StaffRoleGrant
    from portal_api.modules.identity.permissions import ROLE_PERMISSIONS

    reviewing = [r.value for r, perms in ROLE_PERMISSIONS.items() if Permission.review_content in perms]
    clauses: list[Any] = []
    for grant in db.scalars(
        select(StaffRoleGrant).where(
            StaffRoleGrant.user_id == who.user.id,
            StaffRoleGrant.revoked_at.is_(None),
            StaffRoleGrant.role.in_(reviewing),
        )
    ):
        scope = grant.scope or {}
        grades, subjects = scope.get("grades"), scope.get("subjects")
        if grades is None and subjects is None:
            clauses = [true()]
            break
        parts = []
        if grades is not None:
            parts.append(WrittenReviewCase.grade_number.in_(grades))
        if subjects is not None:
            parts.append(WrittenReviewCase.subject_code.in_(subjects))
        clauses.append(and_(*parts))
    return list(
        db.scalars(
            select(WrittenReviewCase)
            .where(WrittenReviewCase.status == "queued", or_(*clauses) if clauses else false())
            .order_by(WrittenReviewCase.opened_at)
            .limit(limit)
        )
    )


def lease(db: Session, who: Principal, case_id: uuid.UUID) -> WrittenReviewCase:
    case = _case(db, who, case_id, lock=True)
    if case.status != "queued":
        raise Conflict("This case has already been released.")
    if case.case_kind == "recheck" and db.scalar(
        select(WrittenScoreVersion.id).where(
            WrittenScoreVersion.attempt_id == case.attempt_id, WrittenScoreVersion.assessor_id == who.user.id
        )
    ):
        # W06.S2.T1: a recheck is an independent second look, never the original marker grading their own work.
        raise Forbidden("A recheck must be marked by a teacher who has not marked this script before.")
    now = _now(db)
    if case.lease_holder not in (None, who.user.id) and case.lease_expires_at and case.lease_expires_at > now:
        raise Conflict("Another teacher is marking this script.", lease_expires_at=case.lease_expires_at.isoformat())
    case.lease_holder = who.user.id
    case.lease_expires_at = now + LEASE
    current = released_result(db, case.attempt_id)
    case.base_version = current.version if current else None
    db.commit()
    db.refresh(case)
    return case


def case_context(db: Session, case: WrittenReviewCase) -> dict[str, Any]:
    """Everything a teacher needs: evidence, mapping and the pinned questions and rubrics. No learner identity."""
    attempt = db.get(WrittenAttempt, case.attempt_id)
    receipt = db.scalar(select(WrittenReceipt).where(WrittenReceipt.attempt_id == case.attempt_id))
    assert attempt is not None and receipt is not None
    form = db.get(WrittenForm, attempt.form_id)
    assert form is not None
    questions = []
    for fi in form.items:
        qv = db.get(ContentVersion, fi.question_version_id)
        rv = db.get(ContentVersion, fi.rubric_version_id)
        assert qv is not None and rv is not None
        questions.append(
            {
                "position": fi.position,
                "max_units": fi.max_units,
                "slots": fi.slots,
                "question": qv.body,
                "rubric": rv.body,
                "rubric_version_id": str(rv.id),
            }
        )
    pages = db.scalars(select(WrittenPage).where(WrittenPage.id.in_([uuid.UUID(p) for p in receipt.page_hashes]))).all()
    return {
        "receipt": receipt,
        "recheck": recheck_request(db, case),
        "manifest": receipt.manifest,
        "questions": questions,
        "pages": sorted(pages, key=lambda p: (p.uploaded_at, str(p.file_id), p.page_index)),
        "max_units": form.max_units,
    }


def latest(db: Session, attempt_id: uuid.UUID) -> WrittenScoreVersion | None:
    return db.scalar(
        select(WrittenScoreVersion)
        .where(WrittenScoreVersion.attempt_id == attempt_id)
        .order_by(WrittenScoreVersion.version.desc())
        .limit(1)
    )


def staff_page(db: Session, who: Principal, case_id: uuid.UUID, page_id: uuid.UUID) -> tuple[bytes, str]:
    case = _case(db, who, case_id)
    receipt = db.scalar(select(WrittenReceipt).where(WrittenReceipt.attempt_id == case.attempt_id))
    page = db.get(WrittenPage, page_id)
    if receipt is None or page is None or str(page_id) not in receipt.page_hashes:
        raise NotFound("Page not found.")
    if page.preview_key is None:
        raise Conflict("This page's preview hasn't been generated yet.", code_reason="PREVIEW_MISSING")
    return storage.get_store().get(page.preview_key), "image/png"


def _check_awards(
    ctx: dict[str, Any], awards: dict[str, dict[str, dict[str, Any]]], scope: set[str] | None = None
) -> tuple[dict[str, int], list[str]]:
    """Validate awards for every question, or only for `scope` (a recheck re-marks just the questions in scope)."""
    errors: list[str] = []
    totals: dict[str, int] = {}
    slots = ctx["manifest"].get("slots", {})
    for q in ctx["questions"]:
        pos = str(q["position"])
        if scope is not None and pos not in scope:
            continue
        rubric, _ = wq.parse_rubric(q["rubric"])
        assert rubric is not None
        given = awards.get(pos, {})
        unknown = set(given) - {c.id for c in rubric.criteria}
        if unknown:
            errors.append(f"Question {pos}: unknown criteria {sorted(unknown)}.")
        earned: dict[str, int] = {}
        for c in rubric.criteria:
            if c.id not in given:
                errors.append(f"Question {pos}: give an award for criterion {c.id}.")
                continue
            units = int(given[c.id].get("units", -1))
            if units not in c.levels:
                errors.append(f"Question {pos} criterion {c.id}: {units} isn't a permitted award {c.levels}.")
                continue
            slot = f"{q['position']}:{c.subpart_id or '*'}"
            if slots.get(slot, {}).get("unanswered") and units != 0:
                errors.append(f"Question {pos} criterion {c.id}: the learner declared this part unanswered.")
            earned[c.id] = units
        for c in rubric.criteria:
            if earned.get(c.id, 0) and any(earned.get(d, 0) == 0 for d in c.depends_on):
                errors.append(f"Question {pos} criterion {c.id} depends on {c.depends_on}, which earned nothing.")
        groups: dict[tuple[str | None, str], list[str]] = {}
        for c in rubric.criteria:
            if c.alternative_group and earned.get(c.id, 0):
                groups.setdefault((c.subpart_id, c.alternative_group), []).append(c.id)
        for (_, group), ids in groups.items():
            if len(ids) > 1:
                errors.append(f"Question {pos}: credit only one route in alternative group {group} (not {ids}).")
        totals[pos] = sum(earned.values())
    return totals, errors


def decide(
    db: Session,
    who: Principal,
    case_id: uuid.UUID,
    *,
    expected_version: int,
    awards: dict[str, dict[str, dict[str, Any]]],
    release: bool,
    reason: str,
    expand_positions: list[int] | None = None,
    expansion_reason: str = "",
    question_status: dict[str, dict[str, Any]] | None = None,
) -> WrittenScoreVersion:
    # One publication per attempt at a time (OCT8-03). Lock order everywhere: attempt row, then case rows.
    visible = _case(db, who, case_id)
    db.scalar(select(WrittenAttempt.id).where(WrittenAttempt.id == visible.attempt_id).with_for_update())
    case = db.scalar(
        select(WrittenReviewCase)
        .where(WrittenReviewCase.id == case_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    assert case is not None
    now = _now(db)
    if case.status != "queued":
        raise Conflict("This case has already been released.")
    if case.lease_holder != who.user.id or (case.lease_expires_at and case.lease_expires_at < now):
        raise Conflict("Take (or renew) the marking lease before saving a decision.")
    if expected_version != case.version:
        raise Conflict(
            "This script was marked by someone else since you opened it. Reload before saving.",
            current_version=case.version,
        )
    ctx = case_context(db, case)
    req: WrittenRecheckRequest | None = ctx["recheck"]
    scope: set[str] | None = None
    current = released_result(db, case.attempt_id)  # authoritative under the attempt lock
    if req is not None:
        assert current is not None
        extra = sorted({int(p) for p in (expand_positions or [])} - set(req.positions))
        valid = {q["position"] for q in ctx["questions"]}
        if set(extra) - valid:
            raise Unprocessable("Only questions on this form can be added to a recheck.")
        if extra:
            if not can_adjudicate(db, who, case):
                raise Forbidden("Only an academic adjudicator can widen a recheck beyond the learner's questions.")
            if len(expansion_reason.strip()) < 10:
                raise Unprocessable("Give a reason for widening the recheck.")
        scope = {str(p) for p in [*req.positions, *req.expanded_positions, *extra]}
        if req.target_version_id != current.id:
            target = db.get(WrittenScoreVersion, req.target_version_id)
            assert target is not None
            changed = sorted(p for p in scope if _question_state(target, p) != _question_state(current, p))
            if changed:
                raise Conflict(
                    "Questions in this recheck changed after it was requested. An academic adjudicator must rebase it.",
                    code_reason="RECHECK_TARGET_CHANGED",
                    changed_positions=[int(p) for p in changed],
                )
            _rebase(db, req, current, None, "only questions outside the recheck changed")
        outside = sorted(set(awards) - scope, key=int)
        if outside:
            raise Unprocessable(
                "This recheck covers only the requested questions. Unaffected marks are carried forward.",
                errors=[f"Question {p} is outside the recheck." for p in outside],
            )
        if extra:
            req.expanded_positions = sorted({*req.expanded_positions, *extra})
            req.expansion_reason = expansion_reason.strip()
            req.expanded_by = who.user.id
    if case.case_kind == "completion":
        # Only questions that are still pending in the current result are marked here.
        assert current is not None
        scope = {str(p) for p in (case.positions or [])}
        outside = sorted(set(awards) - scope, key=int)
        if outside:
            raise Unprocessable(
                "This case covers only the questions that were pending.",
                errors=[f"Question {p} is outside this case." for p in outside],
            )
        no_longer = sorted(p for p in scope if _status_of(current, p) != "pending")
        if no_longer:
            raise Conflict(
                "Some of these questions were resolved by another decision. Reload the script.",
                code_reason="RESULT_CHANGED",
                changed_positions=[int(p) for p in no_longer],
            )
    if (
        scope is not None
        and current is not None
        and case.base_version is not None
        and case.base_version != current.version
    ):
        base = db.scalar(
            select(WrittenScoreVersion).where(
                WrittenScoreVersion.attempt_id == case.attempt_id,
                WrittenScoreVersion.version == case.base_version,
                WrittenScoreVersion.released.is_(True),
            )
        )
        moved = sorted(p for p in scope if base is not None and _question_state(base, p) != _question_state(current, p))
        if moved and req is None:
            raise Conflict(
                "This script's result changed since you opened it. Reload before saving.",
                code_reason="RESULT_CHANGED",
                changed_positions=[int(p) for p in moved],
            )
    # Everything outside this case's questions is carried forward from the *current* released result (OCT8-03).
    carried_awards: dict[str, Any] = {}
    carried_units: dict[str, int] = {}
    carried_status: dict[str, Any] = {}
    if scope is not None and current is not None:
        carried_awards = {p: a for p, a in current.awards.items() if p not in scope}
        carried_units = {p: u for p, u in current.question_units.items() if p not in scope}
        carried_status = {p: st for p, st in (current.question_status or {}).items() if p not in scope}

    # R05: each question in scope is scored, pending (e.g. unreadable, awaiting the learner) or unavailable (the
    # service can't assess it). Pending and unavailable questions get no awards and no invented zero.
    in_scope = [str(q["position"]) for q in ctx["questions"] if scope is None or str(q["position"]) in scope]
    statuses: dict[str, dict[str, Any]] = {}
    for pos in in_scope:
        st = (question_status or {}).get(pos, {"status": "scored"})
        kind = st.get("status", "scored")
        if kind not in QUESTION_STATUSES:
            raise Unprocessable(f"Question {pos}: unknown status {kind!r}.")
        if case.case_kind == "recheck" and kind != "scored":
            raise Unprocessable("A recheck re-marks questions; it can't mark them pending or unavailable.")
        why = str(st.get("reason", "")).strip()
        if kind != "scored" and len(why) < 5:
            raise Unprocessable(f"Question {pos}: give the learner a reason it is {kind}.")
        statuses[pos] = {"status": kind, "reason": why[:500]}
    unknown = sorted(set(question_status or {}) - set(in_scope), key=int)
    if unknown:
        raise Unprocessable("Statuses were given for questions outside this case.", errors=unknown)
    scored = {p for p, st in statuses.items() if st["status"] == "scored"}
    not_scored_awarded = sorted(set(awards) - scored, key=int)
    if not_scored_awarded:
        raise Unprocessable(
            "Pending or unavailable questions can't have awards.", errors=[f"Question {p}" for p in not_scored_awarded]
        )
    totals, errors = _check_awards(ctx, awards, scored)
    if errors:
        raise Unprocessable("Some awards don't follow the rubric.", errors=errors)
    totals = {**carried_units, **totals}
    all_status = {**carried_status, **statuses}
    for q in ctx["questions"]:  # pre-R05 carried questions without an explicit status were scored
        all_status.setdefault(str(q["position"]), {"status": "scored", "reason": ""})
    maxima = {str(q["position"]): int(q["max_units"]) for q in ctx["questions"]}
    pending = sorted(int(p) for p, st in all_status.items() if st["status"] == "pending")
    unavailable = sorted(int(p) for p, st in all_status.items() if st["status"] == "unavailable")
    completeness = "partial_pending" if pending else "partial_unavailable" if unavailable else "complete"
    prior = latest(db, case.attempt_id)
    sv = WrittenScoreVersion(
        attempt_id=case.attempt_id,
        case_id=case.id,
        version=(prior.version + 1) if prior else 1,
        prior_version_id=prior.id if prior else None,
        decision_method="TEACHER",
        case_kind=case.case_kind,
        assessor_id=who.user.id,
        receipt_id=ctx["receipt"].id,
        rubric_version_ids={str(q["position"]): q["rubric_version_id"] for q in ctx["questions"]},
        awards={
            **carried_awards,
            **{
                p: {
                    c: {"units": int(v.get("units", 0)), "reason": str(v.get("reason", ""))[:1000]}
                    for c, v in a.items()
                }
                for p, a in awards.items()
            },
        },
        question_units={p: u for p, u in totals.items() if all_status.get(p, {}).get("status") == "scored"},
        question_status=all_status,
        completeness=completeness,
        scored_max_units=sum(m for p, m in maxima.items() if all_status[p]["status"] == "scored"),
        total_units=sum(u for p, u in totals.items() if all_status.get(p, {}).get("status") == "scored"),
        max_units=ctx["max_units"],
        released=release,
        reason=reason.strip() or case.case_kind,
    )
    db.add(sv)
    case.version += 1
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        raise Conflict(
            "Another decision was published at the same time. Reload the script.", code_reason="RESULT_CHANGED"
        ) from e
    if release:
        from portal_api.modules.access import service as access

        # Allowance (R05): scored questions consume their units once; unavailable ones return theirs; pending hold.
        access.consume(db, case.attempt_id, [int(p) for p in scored])
        access.release_questions(
            db,
            case.attempt_id,
            [int(p) for p, st in statuses.items() if st["status"] == "unavailable"],
            "question unavailable: could not be assessed",
        )
    if release:
        case.status = "released"
        case.released_at = now
        _sync_pending(db, case, set(pending), all_status, now)
    if release:
        if req is not None:
            db.flush()
            req.status = "resolved"
            req.resolved_version_id = sv.id
        case.lease_holder = None
        case.lease_expires_at = None
    record(
        db,
        actor=who.user.id,
        action="written.marked" + (".released" if release else ".saved"),
        target_type="written_attempt",
        target_id=str(case.attempt_id),
        details={
            "case": str(case.id),
            "version": sv.version,
            "total_units": sv.total_units,
            "completeness": completeness,
            "pending": pending,
            "unavailable": unavailable,
        },
    )
    db.commit()
    db.refresh(sv)
    return sv


def _status_of(sv: WrittenScoreVersion, pos: str) -> str:
    return str((sv.question_status or {}).get(pos, {"status": "scored"}).get("status", "scored"))


def _question_state(sv: WrittenScoreVersion, pos: str) -> tuple[str, dict[str, int]]:
    """What a learner or marker sees for one question: its status and awarded units per criterion (not wording)."""
    return _status_of(sv, pos), {c: int(a.get("units", 0)) for c, a in sv.awards.get(pos, {}).items()}


def _rebase(
    db: Session, req: WrittenRecheckRequest, to: WrittenScoreVersion, actor: uuid.UUID | None, reason: str
) -> None:
    """Move an open recheck to the current result, keeping its questions, reason and time (OCT8-03). Audited."""
    old = db.get(WrittenScoreVersion, req.target_version_id)
    req.rebases = [
        *req.rebases,
        {
            "from_version": old.version if old else None,
            "to_version": to.version,
            "at": _now(db).isoformat(),
            "by": str(actor) if actor else "system",
            "reason": reason,
        },
    ]
    req.target_version_id = to.id
    record(
        db,
        actor=actor,
        action="written.recheck_rebased",
        target_type="written_attempt",
        target_id=str(req.attempt_id),
        details={"request": str(req.id), "to_version": to.version, "reason": reason},
    )


def rebase_recheck(db: Session, who: Principal, case_id: uuid.UUID, reason: str) -> WrittenReviewCase:
    """Academic adjudicator path for a recheck whose disputed questions changed after it was requested."""
    visible = _case(db, who, case_id)
    if not can_adjudicate(db, who, visible):
        raise Forbidden("Only an academic adjudicator can rebase a recheck.")
    if len(reason.strip()) < 10:
        raise Unprocessable("Give a reason for rebasing the recheck.")
    db.scalar(select(WrittenAttempt.id).where(WrittenAttempt.id == visible.attempt_id).with_for_update())
    case = db.scalar(
        select(WrittenReviewCase)
        .where(WrittenReviewCase.id == case_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    assert case is not None
    req = recheck_request(db, case)
    current = released_result(db, case.attempt_id)
    if req is None or case.status != "queued" or current is None:
        raise Conflict("Only an open recheck can be rebased.")
    if req.target_version_id != current.id:
        _rebase(db, req, current, who.user.id, reason.strip())
    db.commit()
    db.refresh(case)
    return case


def _sync_pending(
    db: Session, closing: WrittenReviewCase, pending: set[int], status: dict[str, Any], now: datetime
) -> None:
    """After a release, every pending question has exactly one queued completion case (OCT8-02). Questions resolved
    elsewhere leave older cases (closed when empty); uncovered ones get a successor that keeps the original due time."""
    covered: set[int] = set()
    for c in db.scalars(
        select(WrittenReviewCase)
        .where(
            WrittenReviewCase.attempt_id == closing.attempt_id,
            WrittenReviewCase.case_kind == "completion",
            WrittenReviewCase.status == "queued",
            WrittenReviewCase.id != closing.id,
        )
        .order_by(WrittenReviewCase.opened_at)
        .with_for_update()
    ):
        keep = sorted(p for p in (c.positions or []) if p in pending and p not in covered)
        if keep != sorted(c.positions or []):
            c.positions = keep
            c.version += 1  # an in-flight lease on it must reload
            if not keep:
                c.status = "released"
                c.released_at = now
                c.lease_holder = None
                c.lease_expires_at = None
            record(
                db,
                actor=None,
                action="written.completion_rescoped",
                target_type="written_review_case",
                target_id=str(c.id),
                details={"positions": keep},
            )
        covered |= set(keep)
    uncovered = sorted(pending - covered)
    if not uncovered:
        return
    seq = db.scalar(
        select(func.max(WrittenReviewCase.opened_seq)).where(
            WrittenReviewCase.attempt_id == closing.attempt_id, WrittenReviewCase.case_kind == "completion"
        )
    )
    inherited = closing.due_at if closing.case_kind == "completion" else None
    db.add(
        WrittenReviewCase(
            attempt_id=closing.attempt_id,
            case_kind="completion",
            opened_seq=(seq or 0) + 1,
            grade_number=closing.grade_number,
            subject_code=closing.subject_code,
            positions=uncovered,
            reason="; ".join(f"Q{p}: {status[str(p)].get('reason', '')}" for p in uncovered)[:1000],
            due_at=inherited or now + REVIEW_DUE,  # partial progress never resets the service obligation
            predecessor_id=closing.id if closing.case_kind == "completion" else None,
        )
    )


def repair_pending_obligations(db: Session) -> list[str]:
    """Idempotent repair for OCT8-02: give every pending question of a current released result a queued completion
    case. Returns the attempts repaired; each repair is audited. Nothing existing is rewritten."""
    repaired = []
    latest_released = (
        select(WrittenScoreVersion.attempt_id, func.max(WrittenScoreVersion.version).label("v"))
        .where(WrittenScoreVersion.released.is_(True))
        .group_by(WrittenScoreVersion.attempt_id)
        .subquery()
    )
    rows = db.execute(
        select(WrittenScoreVersion)
        .join(
            latest_released,
            (latest_released.c.attempt_id == WrittenScoreVersion.attempt_id)
            & (latest_released.c.v == WrittenScoreVersion.version),
        )
        .where(WrittenScoreVersion.completeness == "partial_pending")
    ).scalars()
    for sv in rows:
        db.scalar(select(WrittenAttempt.id).where(WrittenAttempt.id == sv.attempt_id).with_for_update())
        pending = {int(p) for p in (sv.question_status or {}) if _status_of(sv, p) == "pending"}
        covered = {
            p
            for c in db.scalars(
                select(WrittenReviewCase).where(
                    WrittenReviewCase.attempt_id == sv.attempt_id,
                    WrittenReviewCase.case_kind == "completion",
                    WrittenReviewCase.status == "queued",
                )
            )
            for p in (c.positions or [])
        }
        missing = sorted(pending - covered)
        if not missing:
            continue
        case = db.get(WrittenReviewCase, sv.case_id)
        assert case is not None
        seq = db.scalar(
            select(func.max(WrittenReviewCase.opened_seq)).where(
                WrittenReviewCase.attempt_id == sv.attempt_id, WrittenReviewCase.case_kind == "completion"
            )
        )
        now = _now(db)
        db.add(
            WrittenReviewCase(
                attempt_id=sv.attempt_id,
                case_kind="completion",
                opened_seq=(seq or 0) + 1,
                grade_number=case.grade_number,
                subject_code=case.subject_code,
                positions=missing,
                reason="Repair (OCT8-02): pending questions had no open case",
                due_at=now + REVIEW_DUE,
            )
        )
        record(
            db,
            actor=None,
            action="written.pending_repaired",
            target_type="written_attempt",
            target_id=str(sv.attempt_id),
            details={"positions": missing, "version": sv.version},
        )
        db.commit()
        repaired.append(str(sv.attempt_id))
    return repaired


def released_result(db: Session, attempt_id: uuid.UUID) -> WrittenScoreVersion | None:
    return db.scalar(
        select(WrittenScoreVersion)
        .where(WrittenScoreVersion.attempt_id == attempt_id, WrittenScoreVersion.released.is_(True))
        .order_by(WrittenScoreVersion.version.desc())
        .limit(1)
    )


RECHECK_WINDOW = timedelta(days=14)


def _released(db: Session, attempt_id: uuid.UUID) -> list[WrittenScoreVersion]:
    return list(
        db.scalars(
            select(WrittenScoreVersion)
            .where(WrittenScoreVersion.attempt_id == attempt_id, WrittenScoreVersion.released.is_(True))
            .order_by(WrittenScoreVersion.version)
        )
    )


def appeal_windows(db: Session, attempt_id: uuid.UUID, released: list[WrittenScoreVersion]) -> dict[int, datetime]:
    """Per question: the end of its open appeal window, for questions that may be disputed now (OCT8-04).

    A question's window runs 14 days from the release that last changed its awarded units (its first score counts).
    It closes for that release once a recheck covering it targeted that release or a later one. A completion that
    leaves a question unchanged neither uses nor restarts its appeal; a newly scored question gets its first one.
    """
    if not released:
        return {}
    current = released[-1]
    reqs = list(db.scalars(select(WrittenRecheckRequest).where(WrittenRecheckRequest.attempt_id == attempt_id)))
    version_of = {v.id: v.version for v in released}
    out: dict[int, datetime] = {}
    now = _now(db)
    for pos in sorted({str(p) for v in released for p in (*v.awards, *(v.question_status or {}))}, key=int):
        if _status_of(current, pos) != "scored":
            continue  # pending or unavailable: nothing to dispute yet
        last_change: WrittenScoreVersion | None = None
        prev: tuple[str, dict[str, int]] | None = None
        for v in released:
            state = _question_state(v, pos)
            if state[0] == "scored" and state != prev:
                last_change = v
            prev = state
        if last_change is None:
            continue
        used = any(
            int(pos) in {*r.positions, *r.expanded_positions}
            and version_of.get(r.target_version_id, 0) >= last_change.version
            for r in reqs
        )
        ends = last_change.created_at + RECHECK_WINDOW
        if not used and now <= ends:
            out[int(pos)] = ends
    return out


def recheck_request(db: Session, case: WrittenReviewCase) -> WrittenRecheckRequest | None:
    if case.case_kind != "recheck":
        return None
    return db.scalar(select(WrittenRecheckRequest).where(WrittenRecheckRequest.case_id == case.id))


def recheck_state(db: Session, attempt_id: uuid.UUID) -> dict[str, Any]:
    """Whether and for which questions the learner can ask for a recheck (W06.S2.T1, §20.10, RECHECK-01, OCT8-04)."""
    base: dict[str, Any] = {
        "window_ends_at": None,
        "reason": None,
        "eligible_positions": [],
        "positions": [],
        "target_version": None,
        "closed_reason": None,
        "windows": {},
    }
    released = _released(db, attempt_id)
    if not released:
        return {**base, "status": "unavailable"}
    current = released[-1]
    open_req = db.scalar(
        select(WrittenRecheckRequest).where(
            WrittenRecheckRequest.attempt_id == attempt_id, WrittenRecheckRequest.status == "open"
        )
    )
    if open_req is not None:
        target = db.get(WrittenScoreVersion, open_req.target_version_id)
        return {
            **base,
            "status": "requested",
            "reason": open_req.reason,
            "positions": open_req.positions,
            "target_version": target.version if target else None,
        }
    windows = appeal_windows(db, attempt_id, released)
    base = {**base, "target_version": current.version}
    if windows:
        return {
            **base,
            "status": "available",
            "eligible_positions": sorted(windows),
            "window_ends_at": max(windows.values()),
            "windows": {str(p): w for p, w in windows.items()},
        }
    scored = [p for p in {*current.awards, *(current.question_status or {})} if _status_of(current, p) == "scored"]
    if not scored:
        return {**base, "status": "closed", "closed_reason": "nothing_scored"}
    appealed = db.scalar(select(WrittenRecheckRequest.id).where(WrittenRecheckRequest.attempt_id == attempt_id))
    return {**base, "status": "closed", "closed_reason": "already_rechecked" if appealed else "window_ended"}


def request_recheck(
    db: Session,
    who: Principal,
    attempt_id: uuid.UUID,
    reason: str,
    positions: list[int],
    criteria: dict[str, list[str]] | None = None,
) -> None:
    """Open a recheck case pinned to the current released version. No new allowance is charged."""
    attempt = db.scalar(select(WrittenAttempt).where(WrittenAttempt.id == attempt_id).with_for_update())
    if attempt is None or attempt.user_id != who.user.id:
        raise NotFound("Attempt not found.")
    state = recheck_state(db, attempt_id)
    if state["status"] == "requested":
        raise Conflict("A recheck is already in progress for this script.", code_reason="RECHECK_OPEN")
    if state["status"] == "closed" and state["closed_reason"] in ("window_ended", "nothing_scored"):
        raise Conflict("Rechecks are available for 14 days after your marks are released.", code_reason="WINDOW_ENDED")
    if state["status"] != "available":
        raise Conflict(
            "These marks have already been rechecked. Questions that a correction changed can be appealed.",
            code_reason="ALREADY_RECHECKED",
        )
    chosen = sorted(set(positions))
    eligible = set(state["eligible_positions"])
    if not chosen:
        raise Unprocessable("Choose the question(s) you want rechecked.")
    if not set(chosen) <= eligible:
        raise Unprocessable(
            "Some questions can't be rechecked again.",
            errors=[f"Question {p} isn't open for a recheck." for p in chosen if p not in eligible],
            eligible_positions=sorted(eligible),
        )
    form = db.get(WrittenForm, attempt.form_id)
    assert form is not None
    clean_criteria: dict[str, list[str]] = {}
    for pos, ids in (criteria or {}).items():
        fi = next((f for f in form.items if str(f.position) == str(pos)), None)
        if fi is None or int(pos) not in chosen:
            raise Unprocessable(f"Criteria were given for question {pos}, which isn't part of this recheck.")
        rv = db.get(ContentVersion, fi.rubric_version_id)
        assert rv is not None
        rubric, _ = wq.parse_rubric(rv.body)
        assert rubric is not None
        known = {c.id for c in rubric.criteria}
        if set(ids) - known:
            raise Unprocessable(f"Question {pos} has no criterion {sorted(set(ids) - known)}.")
        if ids:
            clean_criteria[str(pos)] = sorted(set(ids))
    target = released_result(db, attempt_id)
    assert target is not None
    seq = db.scalar(
        select(func.max(WrittenReviewCase.opened_seq)).where(
            WrittenReviewCase.attempt_id == attempt_id, WrittenReviewCase.case_kind == "recheck"
        )
    )
    case = WrittenReviewCase(
        attempt_id=attempt_id,
        case_kind="recheck",
        opened_seq=(seq or 0) + 1,
        grade_number=form.grade_number,
        subject_code=form.subject_code,
        reason=reason.strip(),
        due_at=_now(db) + REVIEW_DUE,
    )
    db.add(case)
    db.flush()
    db.add(
        WrittenRecheckRequest(
            attempt_id=attempt_id,
            case_id=case.id,
            target_version_id=target.id,
            positions=chosen,
            criteria=clean_criteria,
            reason=reason.strip(),
            requested_by=who.user.id,
        )
    )
    try:
        db.flush()
    except IntegrityError as e:  # a concurrent request for the same target won
        db.rollback()
        raise Conflict("A recheck is already in progress for this script.", code_reason="RECHECK_OPEN") from e
    record(
        db,
        actor=who.user.id,
        action="written.recheck_requested",
        target_type="written_attempt",
        target_id=str(attempt_id),
        details={"positions": chosen, "criteria": clean_criteria, "target_version": target.version},
    )
    db.commit()


def released_history(db: Session, attempt_id: uuid.UUID) -> list[WrittenScoreVersion]:
    return list(
        db.scalars(
            select(WrittenScoreVersion)
            .where(WrittenScoreVersion.attempt_id == attempt_id, WrittenScoreVersion.released.is_(True))
            .order_by(WrittenScoreVersion.version)
        )
    )
