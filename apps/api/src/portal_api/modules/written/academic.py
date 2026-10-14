"""Academic review of methods a rubric doesn't cover (W01.S2.T2, W05.S2.T3; ACADEMIC-REVIEW-01; roadmap §20.6.3).

When a teacher finds a valid method the approved marking guide doesn't list, or a problem with the guide itself, the
question is marked **pending** with an `escalation` instead of being forced into a score or quietly marked against a
guide that doesn't fit. Releasing that decision opens one academic review per question. While it is open:

* the learner sees the question pending, with the teacher's reason and that a senior subject reviewer is checking it;
* nobody can mark that question: a completion decision that scores it, or finds it can't be assessed, is refused
  (409 `ACADEMIC_REVIEW_OPEN`), so the guide is never bent to fit one script.

An academic adjudicator for the class and subject, in an MFA session, resolves it:

* `guide_corrected`: an approved correction (W06.S2.T3) of that question's marking guide now covers the method. The
  question is then marked under the corrected guide (completion cases follow the effective guide).
* `not_covered`: the guide stands; the question is marked under it.

Resolution never sets a mark itself. Every raise and resolution is audited; the learner's review rows are in their
data export (without staff identities).
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
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base
from portal_api.errors import Conflict, NotFound, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.identity.deps import Principal

KINDS = ("unlisted_method", "rubric_defect")
RESOLUTIONS = ("guide_corrected", "not_covered")
LEARNER_NOTE = (
    "A senior subject reviewer is checking how the marking guide applies to your answer. This question has no mark "
    "until then, and nothing is counted as zero."
)


class AcademicReview(Base):
    __tablename__ = "written_academic_review"
    __table_args__ = (
        CheckConstraint("kind in ('unlisted_method','rubric_defect')", name="written_academic_review_kind"),
        CheckConstraint("status in ('open','resolved')", name="written_academic_review_status"),
        CheckConstraint(
            "resolution is null or resolution in ('guide_corrected','not_covered')",
            name="written_academic_review_resolution",
        ),
        Index(
            "uq_written_academic_review_open",
            "attempt_id",
            "position",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_attempt.id", ondelete="RESTRICT"), index=True)
    position: Mapped[int] = mapped_column(SmallInteger)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_review_case.id", ondelete="RESTRICT"))
    rubric_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("content_version.id", ondelete="RESTRICT"))
    grade_number: Mapped[int] = mapped_column(SmallInteger)
    subject_code: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)  # what the teacher told the learner and the adjudicator
    raised_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    raised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(10), default="open")
    resolution: Mapped[str | None] = mapped_column(String(20))
    resolution_note: Mapped[str | None] = mapped_column(Text)
    adjudication_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("written_rubric_adjudication.id", ondelete="RESTRICT")
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def check_status(pos: str, status: dict[str, Any], kind: str) -> str | None:
    """Validate an `escalation` on a decision's question status; returns the kind (or None when there is none)."""
    esc = status.get("escalation")
    if esc is None:
        return None
    if esc not in KINDS:
        raise Unprocessable(f"Question {pos}: unknown academic review {esc!r}.")
    if kind != "pending":
        raise Unprocessable(f"Question {pos}: only a pending question can go to academic review.")
    if status.get("learner_action") is not None:
        raise Unprocessable(f"Question {pos}: ask the learner or send it to academic review, not both.")
    return str(esc)


def open_positions(db: Session, attempt_id: uuid.UUID) -> dict[int, AcademicReview]:
    return {
        r.position: r
        for r in db.scalars(
            select(AcademicReview).where(AcademicReview.attempt_id == attempt_id, AcademicReview.status == "open")
        )
    }


def guard_marking(db: Session, attempt_id: uuid.UUID, decided: dict[str, dict[str, Any]]) -> None:
    """No question under open academic review is scored or closed as unassessable until it is resolved."""
    blocked = sorted(
        p for p in open_positions(db, attempt_id) if decided.get(str(p), {}).get("status") in ("scored", "unavailable")
    )
    if blocked:
        raise Conflict(
            "A senior subject reviewer hasn't yet decided how the marking guide applies to "
            f"question {', '.join(map(str, blocked))}. Leave it pending until the academic review is resolved.",
            code_reason="ACADEMIC_REVIEW_OPEN",
            positions=blocked,
        )


def raise_for(
    db: Session,
    who: Principal,
    case: Any,
    statuses: dict[str, dict[str, Any]],
    rubric_versions: dict[str, str],
) -> list[int]:
    """On release: one open review per escalated question (idempotent: an open one is kept). Returns new positions."""
    opened = []
    for pos, st in statuses.items():
        kind = st.get("escalation")
        if not kind:
            continue
        rid = rubric_versions.get(pos)
        row = db.execute(
            insert(AcademicReview)
            .values(
                id=uuid.uuid4(),
                attempt_id=case.attempt_id,
                position=int(pos),
                case_id=case.id,
                rubric_version_id=uuid.UUID(rid) if rid else None,
                grade_number=case.grade_number,
                subject_code=case.subject_code,
                kind=kind,
                reason=str(st.get("reason", ""))[:500],
                raised_by=who.user.id,
                status="open",
            )
            .on_conflict_do_nothing(index_elements=["attempt_id", "position"], index_where=text("status = 'open'"))
            .returning(AcademicReview.id)
        ).first()
        if row is None:
            continue
        opened.append(int(pos))
        record(
            db,
            actor=who.user.id,
            action="written.academic_review_opened",
            target_type="written_attempt",
            target_id=str(case.attempt_id),
            details={"review": str(row[0]), "position": int(pos), "kind": kind},
        )
    return opened


def visible(db: Session, who: Principal, status: str = "open", limit: int = 100) -> list[AcademicReview]:
    """Reviews in the caller's academic scope (the same scope as rubric corrections), oldest first."""
    from portal_api.modules.written import adjudication

    scope = adjudication.scope_clause(db, who, AcademicReview.grade_number, AcademicReview.subject_code)
    return list(
        db.scalars(
            select(AcademicReview)
            .where(scope, AcademicReview.status == status)
            .order_by(AcademicReview.raised_at, AcademicReview.id)
            .limit(limit)
        )
    )


def resolve(
    db: Session,
    who: Principal,
    review_id: uuid.UUID,
    resolution: str,
    note: str,
    adjudication_id: uuid.UUID | None,
) -> AcademicReview:
    from portal_api.modules.content.models import ContentVersion
    from portal_api.modules.written import adjudication

    review = db.get(AcademicReview, review_id, with_for_update=True)
    if review is None:
        raise NotFound("Academic review not found.")
    adjudication.require_adjudicator(db, who, review.grade_number, review.subject_code)
    if review.status != "open":
        raise Conflict("This academic review is already resolved.", code_reason="ALREADY_RESOLVED")
    if resolution not in RESOLUTIONS:
        raise Unprocessable(f"Unknown resolution {resolution!r}.")
    if resolution == "guide_corrected":
        adj = db.get(adjudication.RubricAdjudication, adjudication_id) if adjudication_id else None
        pinned = db.get(ContentVersion, review.rubric_version_id) if review.rubric_version_id else None
        if (
            adj is None
            or adj.status != "active"
            or pinned is None
            or adj.rubric_item_id != pinned.item_id
            or str(pinned.id) not in adj.from_version_ids
        ):
            raise Unprocessable(
                "Name the approved correction of this question's marking guide that covers the method.",
                code_reason="CORRECTION_REQUIRED",
            )
    elif adjudication_id is not None:
        raise Unprocessable("Only a corrected guide names a correction.")
    review.status = "resolved"
    review.resolution = resolution
    review.resolution_note = note.strip()
    review.adjudication_id = adjudication_id
    review.resolved_by = who.user.id
    review.resolved_at = func.now()
    record(
        db,
        actor=who.user.id,
        action="written.academic_review_resolved",
        target_type="written_attempt",
        target_id=str(review.attempt_id),
        details={
            "review": str(review.id),
            "position": review.position,
            "resolution": resolution,
            "note": note.strip(),
            "adjudication": str(adjudication_id) if adjudication_id else None,
        },
    )
    db.commit()
    db.refresh(review)
    return review
