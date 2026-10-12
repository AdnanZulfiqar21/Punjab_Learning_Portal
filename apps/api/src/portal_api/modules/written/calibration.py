"""Independent calibration of automatic proposals against blinded teacher marking (roadmap W06.S1.T3; CALIBRATION-01).

Automatic assessment stays disabled for learners (B10; WG10). Calibration is how it would ever earn trust:

* **Evaluation subset:** a fixed, deterministic share of sealed scripts (`written_evaluation_percent`, by a hash of the
  attempt id, so the same script is always in or out).
* **Blinded marking:** teachers never see an automatic proposal. The marking workspace has no path to one, so the
  teacher's first released decision on the script's initial case is an independent label.
* **Comparison:** once that decision is released, each question's validated proposal for the same sealed evidence and
  rubric version is compared criterion by criterion. Agreement and every disagreement are recorded.
* **Adjudication:** an academic adjudicator in scope (MFA) records, for each disagreement, whether the teacher, the
  proposal, both or neither applied the rubric correctly, with a reason. This never changes the teacher's score
  version, the learner's result or the proposal: it is evidence for the WG10 reliability gate only.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, String, Text, UniqueConstraint, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID, insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.config import get_settings
from portal_api.db import Base, get_session
from portal_api.errors import Conflict, Forbidden, NotFound, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.content.workflow import roles_in_scope
from portal_api.modules.identity.deps import Principal, require
from portal_api.modules.identity.permissions import Permission, permissions_for
from portal_api.modules.written.automatic import AutoAssessment
from portal_api.modules.written.models import WrittenAttempt, WrittenForm
from portal_api.modules.written.review import WrittenReviewCase, WrittenScoreVersion

router = APIRouter(prefix="/v1/studio/written", tags=["written-calibration"])
DB = Annotated[Session, Depends(get_session)]
Adjudicator = Annotated[Principal, Depends(require(Permission.adjudicate))]
VERDICTS = ("teacher", "proposal", "both", "neither")


class CalibrationComparison(Base):
    """One question of one evaluation script: the teacher's blinded awards beside the automatic proposal."""

    __tablename__ = "written_calibration"
    __table_args__ = (
        UniqueConstraint("score_version_id", "auto_assessment_id", name="uq_written_calibration_pair"),
        CheckConstraint("status in ('agreed','open','adjudicated')", name="written_calibration_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_attempt.id", ondelete="RESTRICT"), index=True)
    grade_number: Mapped[int] = mapped_column(SmallInteger)
    subject_code: Mapped[str] = mapped_column(String(40))
    position: Mapped[int] = mapped_column(SmallInteger)
    score_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_score_version.id", ondelete="RESTRICT"))
    auto_assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_auto_assessment.id", ondelete="RESTRICT"))
    teacher_units: Mapped[dict[str, int]] = mapped_column(JSONB)
    proposal_units: Mapped[dict[str, int]] = mapped_column(JSONB)
    disagreements: Mapped[list[str]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(12))
    verdicts: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict)
    reason: Mapped[str | None] = mapped_column(Text)
    adjudicated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    adjudicated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def in_evaluation_subset(attempt_id: uuid.UUID, percent: int | None = None) -> bool:
    share = get_settings().written_evaluation_percent if percent is None else percent
    return int(hashlib.sha256(str(attempt_id).encode()).hexdigest()[:8], 16) % 100 < share


def refresh(db: Session, grade: int, subject: str) -> int:
    """Record comparisons for released, blinded teacher decisions that have a validated proposal (idempotent)."""
    first_release = (
        select(WrittenScoreVersion)
        .join(WrittenReviewCase, WrittenReviewCase.id == WrittenScoreVersion.case_id)
        .join(WrittenAttempt, WrittenAttempt.id == WrittenScoreVersion.attempt_id)
        .join(WrittenForm, WrittenForm.id == WrittenAttempt.form_id)
        .where(
            WrittenScoreVersion.released.is_(True),
            WrittenScoreVersion.decision_method == "TEACHER",
            WrittenReviewCase.case_kind == "initial",
            WrittenForm.grade_number == grade,
            WrittenForm.subject_code == subject,
        )
        .order_by(WrittenScoreVersion.attempt_id, WrittenScoreVersion.version)
    )
    seen: set[uuid.UUID] = set()
    created = 0
    for sv in db.scalars(first_release):
        if sv.attempt_id in seen or not in_evaluation_subset(sv.attempt_id):
            continue
        seen.add(sv.attempt_id)
        proposals = db.scalars(
            select(AutoAssessment).where(
                AutoAssessment.receipt_id == sv.receipt_id, AutoAssessment.status == "proposed"
            )
        )
        for p in proposals:
            pos = str(p.position)
            if str(sv.rubric_version_ids.get(pos)) != str(p.rubric_version_id) or pos not in sv.awards:
                continue  # a different rubric version or an unscored question: not the same judgement
            teacher = {c: int(a.get("units", 0)) for c, a in sv.awards[pos].items()}
            proposed = {c: int(a.get("units", 0)) for c, a in (p.proposal.get("awards") or {}).items()}
            differ = sorted(c for c in set(teacher) | set(proposed) if teacher.get(c) != proposed.get(c))
            res = db.execute(
                insert(CalibrationComparison)
                .values(
                    id=uuid.uuid4(),
                    attempt_id=sv.attempt_id,
                    grade_number=grade,
                    subject_code=subject,
                    position=p.position,
                    score_version_id=sv.id,
                    auto_assessment_id=p.id,
                    teacher_units=teacher,
                    proposal_units=proposed,
                    disagreements=differ,
                    status="open" if differ else "agreed",
                    verdicts={},
                )
                .on_conflict_do_nothing(constraint="uq_written_calibration_pair")
                .returning(CalibrationComparison.id)
            )
            created += len(res.all())
    db.commit()
    return created


class ComparisonOut(BaseModel):
    id: uuid.UUID
    reference: str = Field(description="The script's short reference; no learner identity")
    position: int
    teacher_units: dict[str, int]
    proposal_units: dict[str, int]
    disagreements: list[str]
    status: Literal["agreed", "open", "adjudicated"]
    verdicts: dict[str, str]
    reason: str | None


class CalibrationOut(BaseModel):
    evaluation_percent: int
    compared: int
    agreed: int
    disagreed: int
    adjudicated: int
    agreement_rate: float | None = Field(description="Share of compared questions with identical awards")
    comparisons: list[ComparisonOut]


class AdjudicateIn(BaseModel):
    verdicts: dict[str, Literal["teacher", "proposal", "both", "neither"]] = Field(
        description="For each disputed criterion: who applied the rubric correctly"
    )
    reason: str = Field(min_length=10, max_length=2000)


def _in_scope(db: Session, who: Principal, grade: int, subject: str) -> None:
    if Permission.adjudicate not in permissions_for(roles_in_scope(db, who.user.id, grade, subject)):
        raise Forbidden("Calibration in this class and subject is for its academic adjudicators.")


def _out(c: CalibrationComparison) -> ComparisonOut:
    return ComparisonOut(
        id=c.id,
        reference=str(c.attempt_id)[:8],
        position=c.position,
        teacher_units=c.teacher_units,
        proposal_units=c.proposal_units,
        disagreements=c.disagreements,
        status=c.status,  # type: ignore[arg-type]
        verdicts=c.verdicts or {},
        reason=c.reason,
    )


@router.get(
    "/calibration",
    response_model=CalibrationOut,
    summary="Blinded teacher marking compared with automatic proposals on the evaluation subset (adjudicators, MFA)",
)
def calibration(
    db: DB,
    who: Adjudicator,
    response: Response,
    grade: Annotated[int, Query(ge=11, le=12)],
    subject: Annotated[str, Query(min_length=2, max_length=40)],
) -> CalibrationOut:
    response.headers["Cache-Control"] = "private, no-store"
    _in_scope(db, who, grade, subject)
    refresh(db, grade, subject)
    rows = list(
        db.scalars(
            select(CalibrationComparison)
            .where(CalibrationComparison.grade_number == grade, CalibrationComparison.subject_code == subject)
            .order_by(CalibrationComparison.status.desc(), CalibrationComparison.created_at)
        )
    )
    agreed = sum(1 for r in rows if r.status == "agreed")
    return CalibrationOut(
        evaluation_percent=get_settings().written_evaluation_percent,
        compared=len(rows),
        agreed=agreed,
        disagreed=len(rows) - agreed,
        adjudicated=sum(1 for r in rows if r.status == "adjudicated"),
        agreement_rate=round(agreed / len(rows), 4) if rows else None,
        comparisons=[_out(r) for r in rows],
    )


@router.post(
    "/calibration/{comparison_id}/adjudicate",
    response_model=ComparisonOut,
    summary="Record who applied the rubric correctly in each disagreement (adjudicators, MFA; audited)",
    description="Evidence for the reliability gate only: the teacher's score version and the learner's result "
    "stay as they are.",
)
def adjudicate(db: DB, who: Adjudicator, comparison_id: uuid.UUID, body: AdjudicateIn) -> ComparisonOut:
    c = db.get(CalibrationComparison, comparison_id, with_for_update=True)
    if c is None:
        raise NotFound("Comparison not found.")
    _in_scope(db, who, c.grade_number, c.subject_code)
    if c.status != "open":
        raise Conflict(
            "Only an open disagreement can be adjudicated." if c.status == "agreed" else "Already adjudicated."
        )
    if set(body.verdicts) != set(c.disagreements):
        raise Unprocessable("Give one verdict for each disputed criterion, and only those.", expected=c.disagreements)
    c.verdicts, c.reason = dict(body.verdicts), body.reason.strip()
    c.status, c.adjudicated_by, c.adjudicated_at = "adjudicated", who.user.id, func.now()
    record(
        db,
        actor=who.user.id,
        action="written.calibration_adjudicated",
        target_type="written_calibration",
        target_id=str(c.id),
        details={"verdicts": c.verdicts, "reason": c.reason},
    )
    db.commit()
    db.refresh(c)
    return _out(c)
