"""Teacher marking API (W06.S1) and the learner's released result (W07.S1.T1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from portal_api.db import get_session
from portal_api.errors import NotFound
from portal_api.modules.content import written as wq
from portal_api.modules.content.models import ContentVersion
from portal_api.modules.identity.deps import CurrentPrincipal, Principal, require
from portal_api.modules.identity.permissions import Permission
from portal_api.modules.written import review
from portal_api.modules.written.models import WrittenAttempt, WrittenForm
from portal_api.modules.written.schemas import PageOut

router = APIRouter(prefix="/v1", tags=["written marking"])
DB = Annotated[Session, Depends(get_session)]
Reviewer = Annotated[Principal, Depends(require(Permission.review_content))]


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


class CaseSummary(BaseModel):
    id: uuid.UUID
    reference: str = Field(description="Short script reference; learner identity is not shown to markers")
    grade: int
    subject: str
    case_kind: Literal["initial", "recheck"]
    opened_at: datetime
    status: Literal["queued", "released"]
    version: int
    leased_by_me: bool
    leased_by_other: bool


class CaseQuestion(BaseModel):
    position: int
    max_units: int
    slots: list[str]
    question: dict[str, Any]
    rubric: dict[str, Any]
    rubric_version_id: uuid.UUID


class StaffScore(BaseModel):
    version: int
    total_units: int
    max_units: int
    question_units: dict[str, int]
    awards: dict[str, Any]
    released: bool
    reason: str
    created_at: datetime


class CaseDetail(CaseSummary):
    max_units: int
    manifest: dict[str, Any]
    questions: list[CaseQuestion]
    pages: list[PageOut]
    lease_expires_at: datetime | None
    latest: StaffScore | None


class DecisionIn(BaseModel):
    expected_version: int = Field(ge=0)
    awards: dict[str, dict[str, dict[str, Any]]] = Field(description='{"1": {"a1": {"units": 100, "reason": "…"}}}')
    release: bool = False
    reason: str = Field(default="", max_length=1000)


class CriterionResult(BaseModel):
    id: str
    subpart_id: str | None
    description: str
    earned_units: int
    max_units: int
    reason: str


class QuestionResult(BaseModel):
    position: int
    max_units: int
    earned_units: int
    criteria: list[CriterionResult]


class WrittenResultOut(BaseModel):
    status: Literal["pending", "released"]
    version: int | None
    total_units: int | None
    max_units: int
    released_at: datetime | None
    decision_method: str | None
    questions: list[QuestionResult]


def _summary(case: review.WrittenReviewCase, who: Principal) -> dict[str, Any]:
    now = datetime.now(tz=case.opened_at.tzinfo)
    leased = case.lease_holder is not None and case.lease_expires_at is not None and case.lease_expires_at > now
    return {
        "id": case.id,
        "reference": str(case.attempt_id)[:8],
        "grade": case.grade_number,
        "subject": case.subject_code,
        "case_kind": case.case_kind,
        "opened_at": case.opened_at,
        "status": case.status,
        "version": case.version,
        "leased_by_me": leased and case.lease_holder == who.user.id,
        "leased_by_other": leased and case.lease_holder != who.user.id,
    }


def _staff_score(sv: review.WrittenScoreVersion | None) -> StaffScore | None:
    if sv is None:
        return None
    return StaffScore(
        version=sv.version,
        total_units=sv.total_units,
        max_units=sv.max_units,
        question_units=sv.question_units,
        awards=sv.awards,
        released=sv.released,
        reason=sv.reason,
        created_at=sv.created_at,
    )


def _detail(db: Session, case: review.WrittenReviewCase, who: Principal) -> CaseDetail:
    ctx = review.case_context(db, case)
    return CaseDetail(
        **_summary(case, who),
        max_units=ctx["max_units"],
        manifest=ctx["manifest"],
        questions=[CaseQuestion(**q) for q in ctx["questions"]],
        pages=[
            PageOut(
                id=p.id,
                size=p.size,
                content_type=p.content_type,
                width=p.width,
                height=p.height,
                pdf_pages=p.pdf_pages,
                uploaded_at=p.uploaded_at,
            )
            for p in ctx["pages"]
        ],
        lease_expires_at=case.lease_expires_at,
        latest=_staff_score(review.latest(db, case.attempt_id)),
    )


@router.get("/studio/written/queue", response_model=list[CaseSummary], summary="Scripts awaiting marking in your scope")
def marking_queue(db: DB, who: Reviewer, response: Response) -> list[CaseSummary]:
    _private(response)
    return [CaseSummary(**_summary(c, who)) for c in review.queue(db, who)]


@router.get("/studio/written/cases/{case_id}", response_model=CaseDetail)
def case_detail(db: DB, who: Reviewer, case_id: uuid.UUID, response: Response) -> CaseDetail:
    _private(response)
    return _detail(db, review.get_case(db, who, case_id), who)


@router.post(
    "/studio/written/cases/{case_id}/lease", response_model=CaseDetail, summary="Take or renew the marking lease"
)
def take_lease(db: DB, who: Reviewer, case_id: uuid.UUID, response: Response) -> CaseDetail:
    _private(response)
    return _detail(db, review.lease(db, who, case_id), who)


@router.get("/studio/written/cases/{case_id}/pages/{page_id}", summary="Submitted evidence page (markers in scope)")
def case_page(db: DB, who: Reviewer, case_id: uuid.UUID, page_id: uuid.UUID) -> Response:
    data, content_type = review.staff_page(db, who, case_id, page_id)
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post(
    "/studio/written/cases/{case_id}/decision",
    response_model=CaseDetail,
    summary="Save or release marks (expected-version CAS; awards must be permitted rubric levels)",
)
def decision(db: DB, who: Reviewer, case_id: uuid.UUID, body: DecisionIn, response: Response) -> CaseDetail:
    _private(response)
    review.decide(
        db,
        who,
        case_id,
        expected_version=body.expected_version,
        awards=body.awards,
        release=body.release,
        reason=body.reason,
    )
    return _detail(db, review.get_case(db, who, case_id), who)


@router.get(
    "/written-attempts/{attempt_id}/result",
    response_model=WrittenResultOut,
    summary="Your marks, once a teacher has released them",
)
def my_result(db: DB, who: CurrentPrincipal, attempt_id: uuid.UUID, response: Response) -> WrittenResultOut:
    _private(response)
    attempt = db.get(WrittenAttempt, attempt_id)
    if attempt is None or attempt.user_id != who.user.id:
        raise NotFound("Attempt not found.")
    form = db.get(WrittenForm, attempt.form_id)
    assert form is not None
    sv = review.released_result(db, attempt.id)
    if sv is None:
        return WrittenResultOut(
            status="pending",
            version=None,
            total_units=None,
            max_units=form.max_units,
            released_at=None,
            decision_method=None,
            questions=[],
        )
    ctx_questions = {str(fi.position): fi for fi in form.items}
    questions = []
    for pos, fi in sorted(ctx_questions.items(), key=lambda kv: int(kv[0])):
        rv = db.get(ContentVersion, fi.rubric_version_id)
        assert rv is not None
        rubric, _ = wq.parse_rubric(rv.body)
        assert rubric is not None
        given = sv.awards.get(pos, {})
        questions.append(
            QuestionResult(
                position=fi.position,
                max_units=fi.max_units,
                earned_units=sv.question_units.get(pos, 0),
                criteria=[
                    CriterionResult(
                        id=c.id,
                        subpart_id=c.subpart_id,
                        description=c.description,
                        earned_units=int(given.get(c.id, {}).get("units", 0)),
                        max_units=c.max_units,
                        reason=str(given.get(c.id, {}).get("reason", "")),
                    )
                    for c in rubric.criteria
                ],
            )
        )
    return WrittenResultOut(
        status="released",
        version=sv.version,
        total_units=sv.total_units,
        max_units=sv.max_units,
        released_at=sv.created_at,
        decision_method=sv.decision_method,
        questions=questions,
    )
