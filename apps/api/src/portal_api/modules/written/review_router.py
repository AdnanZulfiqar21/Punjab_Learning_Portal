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
from portal_api.modules.written.router import pages_out
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


class RecheckScope(BaseModel):
    target_version: int = Field(description="The released version the learner disputes")
    positions: list[int] = Field(description="Questions the learner asked to be rechecked")
    criteria: dict[str, list[str]] = Field(description="Optional disputed criteria per question")
    reason: str
    expanded_positions: list[int] = Field(description="Questions an adjudicator added, with a recorded reason")
    can_expand: bool = Field(description="Whether you may widen the recheck (academic adjudicators only)")
    carried_forward: dict[str, int] = Field(description="Earned units kept unchanged for questions outside the scope")


class CaseDetail(CaseSummary):
    max_units: int
    manifest: dict[str, Any]
    questions: list[CaseQuestion]
    pages: list[PageOut]
    lease_expires_at: datetime | None
    latest: StaffScore | None
    recheck: RecheckScope | None


class DecisionIn(BaseModel):
    expected_version: int = Field(ge=0)
    awards: dict[str, dict[str, dict[str, Any]]] = Field(description='{"1": {"a1": {"units": 100, "reason": "…"}}}')
    release: bool = False
    reason: str = Field(default="", max_length=1000)
    expand_positions: list[int] = Field(
        default_factory=list, max_length=20, description="Recheck only: questions to add (academic adjudicators)"
    )
    expansion_reason: str = Field(default="", max_length=1000)


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


class RecheckOut(BaseModel):
    status: Literal["unavailable", "available", "requested", "closed"]
    window_ends_at: datetime | None = Field(description="14 days after the disputed result was released")
    reason: str | None
    eligible_positions: list[int] = Field(description="Questions that can be disputed now (when available)")
    positions: list[int] = Field(description="Questions in the open request (when requested)")
    target_version: int | None = Field(description="The released version a request targets")
    closed_reason: Literal["window_ended", "already_rechecked", "no_corrected_questions"] | None


class HistoryEntry(BaseModel):
    version: int
    total_units: int
    case_kind: str
    released_at: datetime


class RecheckIn(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)
    positions: list[int] = Field(min_length=1, max_length=20)
    criteria: dict[str, list[str]] = Field(
        default_factory=dict, description="Optional: disputed criterion ids per question position"
    )


class WrittenResultOut(BaseModel):
    status: Literal["pending", "released"]
    version: int | None
    total_units: int | None
    max_units: int
    released_at: datetime | None
    decision_method: str | None
    questions: list[QuestionResult]
    recheck: RecheckOut
    history: list[HistoryEntry] = Field(
        description="Every released version, oldest first; corrections never erase history"
    )


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
        pages=pages_out(db, ctx["pages"]),
        lease_expires_at=case.lease_expires_at,
        latest=_staff_score(review.latest(db, case.attempt_id)),
        recheck=_recheck_scope(db, ctx["recheck"], case, who),
    )


def _recheck_scope(
    db: Session, req: review.WrittenRecheckRequest | None, case: review.WrittenReviewCase, who: Principal
) -> RecheckScope | None:
    if req is None:
        return None
    target = db.get(review.WrittenScoreVersion, req.target_version_id)
    assert target is not None
    scope = {str(p) for p in [*req.positions, *req.expanded_positions]}
    return RecheckScope(
        target_version=target.version,
        positions=req.positions,
        criteria=req.criteria,
        reason=req.reason,
        expanded_positions=req.expanded_positions,
        can_expand=review.can_adjudicate(db, who, case),
        carried_forward={p: u for p, u in target.question_units.items() if p not in scope},
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
        expand_positions=body.expand_positions,
        expansion_reason=body.expansion_reason,
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
            recheck=RecheckOut(**review.recheck_state(db, attempt.id)),
            history=[],
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
    history = [
        HistoryEntry(version=h.version, total_units=h.total_units, case_kind=h.case_kind, released_at=h.created_at)
        for h in review.released_history(db, attempt.id)
    ]
    return WrittenResultOut(
        status="released",
        version=sv.version,
        total_units=sv.total_units,
        max_units=sv.max_units,
        released_at=sv.created_at,
        decision_method=sv.decision_method,
        questions=questions,
        recheck=RecheckOut(**review.recheck_state(db, attempt.id)),
        history=history,
    )


@router.post(
    "/written-attempts/{attempt_id}/recheck",
    response_model=RecheckOut,
    summary="Ask a teacher to recheck released marks (same evidence; no extra allowance)",
)
def request_recheck(
    db: DB, who: CurrentPrincipal, attempt_id: uuid.UUID, body: RecheckIn, response: Response
) -> RecheckOut:
    _private(response)
    review.request_recheck(db, who, attempt_id, body.reason, body.positions, body.criteria)
    return RecheckOut(**review.recheck_state(db, attempt_id))
