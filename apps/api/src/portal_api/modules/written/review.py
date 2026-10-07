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
    ctx: dict[str, Any], awards: dict[str, dict[str, dict[str, Any]]]
) -> tuple[dict[str, int], list[str]]:
    errors: list[str] = []
    totals: dict[str, int] = {}
    slots = ctx["manifest"].get("slots", {})
    for q in ctx["questions"]:
        pos = str(q["position"])
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
    totals, errors = _check_awards(ctx, awards)
    if errors:
        raise Unprocessable("Some awards don't follow the rubric.", errors=errors)
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
            p: {c: {"units": int(v.get("units", 0)), "reason": str(v.get("reason", ""))[:1000]} for c, v in a.items()}
            for p, a in awards.items()
        },
        question_units=totals,
        total_units=sum(totals.values()),
        max_units=ctx["max_units"],
        released=release,
        reason=reason.strip() or case.case_kind,
    )
    db.add(sv)
    case.version += 1
    if release:
        case.status = "released"
        case.released_at = now
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
