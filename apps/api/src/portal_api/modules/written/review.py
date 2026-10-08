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


class WrittenReviewCase(Base):
    __tablename__ = "written_review_case"
    __table_args__ = (
        UniqueConstraint("attempt_id", "case_kind", "opened_seq", name="uq_written_case"),
        CheckConstraint("status in ('queued','released')", name="written_case_status"),
        CheckConstraint("case_kind in ('initial','recheck')", name="written_case_kind"),
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
    question_units: Mapped[dict[str, int]] = mapped_column(JSONB)  # position -> earned units
    total_units: Mapped[int] = mapped_column(Integer)
    max_units: Mapped[int] = mapped_column(Integer)
    released: Mapped[bool] = mapped_column(default=False)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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
        )
    )


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
        "pages": sorted(pages, key=lambda p: (p.uploaded_at, str(p.id))),
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
    return storage.get_store().get(page.storage_key), page.content_type


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
) -> WrittenScoreVersion:
    case = _case(db, who, case_id, lock=True)
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
    carried_awards: dict[str, Any] = {}
    carried_units: dict[str, int] = {}
    scope: set[str] | None = None
    if req is not None:
        target = db.get(WrittenScoreVersion, req.target_version_id)
        current = released_result(db, case.attempt_id)
        assert target is not None
        if current is None or current.id != target.id:
            raise Conflict(
                "The released result changed after this recheck was requested. It needs academic review.",
                code_reason="RECHECK_TARGET_STALE",
            )
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
        outside = sorted(set(awards) - scope, key=int)
        if outside:
            raise Unprocessable(
                "This recheck covers only the requested questions. Unaffected marks are carried forward.",
                errors=[f"Question {p} is outside the recheck." for p in outside],
            )
        carried_awards = {p: a for p, a in target.awards.items() if p not in scope}
        carried_units = {p: u for p, u in target.question_units.items() if p not in scope}
        if extra:
            req.expanded_positions = sorted({*req.expanded_positions, *extra})
            req.expansion_reason = expansion_reason.strip()
            req.expanded_by = who.user.id
    totals, errors = _check_awards(ctx, awards, scope)
    if errors:
        raise Unprocessable("Some awards don't follow the rubric.", errors=errors)
    totals = {**carried_units, **totals}
    prior = latest(db, case.attempt_id)
    first_release = release and released_result(db, case.attempt_id) is None
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
        question_units=totals,
        total_units=sum(totals.values()),
        max_units=ctx["max_units"],
        released=release,
        reason=reason.strip() or case.case_kind,
    )
    db.add(sv)
    case.version += 1
    if first_release:
        from portal_api.modules.access import service as access

        access.consume(db, case.attempt_id)  # once, on the first released marks for this original work
    if release:
        case.status = "released"
        case.released_at = now
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
        details={"case": str(case.id), "version": sv.version, "total_units": sv.total_units},
    )
    db.commit()
    db.refresh(sv)
    return sv


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


def _eligible_positions(db: Session, attempt_id: uuid.UUID, released: list[WrittenScoreVersion]) -> list[int]:
    """Questions a learner may dispute on the current result (RECHECK-01).

    A first result: every question. A corrected result: the questions whose awards that correction changed. Unchanged
    questions already had an independent second look, so asking again would be a duplicate, not a new appeal.
    """
    current = released[-1]
    if len(released) == 1:
        attempt = db.get(WrittenAttempt, attempt_id)
        assert attempt is not None
        form = db.get(WrittenForm, attempt.form_id)
        assert form is not None
        return sorted(fi.position for fi in form.items)
    prev = released[-2]

    def units(sv: WrittenScoreVersion, pos: str) -> dict[str, int]:
        return {c: int(a.get("units", 0)) for c, a in sv.awards.get(pos, {}).items()}

    # Only a change in awarded marks opens a new appeal; reworded feedback on an upheld mark does not.
    keys = set(current.awards) | set(prev.awards)
    return sorted(int(p) for p in keys if units(current, p) != units(prev, p))


def recheck_request(db: Session, case: WrittenReviewCase) -> WrittenRecheckRequest | None:
    if case.case_kind != "recheck":
        return None
    return db.scalar(select(WrittenRecheckRequest).where(WrittenRecheckRequest.case_id == case.id))


def recheck_state(db: Session, attempt_id: uuid.UUID) -> dict[str, Any]:
    """Whether and for which questions the learner can ask for a recheck (W06.S2.T1, §20.10, RECHECK-01).

    The window is 14 days from the release of the result being disputed, so a later correction can itself be appealed.
    """
    base: dict[str, Any] = {
        "window_ends_at": None,
        "reason": None,
        "eligible_positions": [],
        "positions": [],
        "target_version": None,
        "closed_reason": None,
    }
    released = _released(db, attempt_id)
    if not released:
        return {**base, "status": "unavailable"}
    current = released[-1]
    ends = current.created_at + RECHECK_WINDOW
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
            "window_ends_at": ends,
            "reason": open_req.reason,
            "positions": open_req.positions,
            "target_version": target.version if target else None,
        }
    base = {**base, "window_ends_at": ends, "target_version": current.version}
    if db.scalar(select(WrittenRecheckRequest.id).where(WrittenRecheckRequest.target_version_id == current.id)):
        return {**base, "status": "closed", "closed_reason": "already_rechecked"}
    eligible = _eligible_positions(db, attempt_id, released)
    if not eligible:
        return {**base, "status": "closed", "closed_reason": "no_corrected_questions"}
    if _now(db) > ends:
        return {**base, "status": "closed", "closed_reason": "window_ended"}
    return {**base, "status": "available", "eligible_positions": eligible}


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
    if state["status"] == "closed" and state["closed_reason"] == "window_ended":
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
