"""Teacher marking API (W06.S1) and the learner's released result (W07.S1.T1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from portal_api.db import get_session
from portal_api.errors import NotFound
from portal_api.modules.content import written as wq
from portal_api.modules.content.models import ContentVersion
from portal_api.modules.identity.deps import CurrentPrincipal, Principal, require
from portal_api.modules.identity.permissions import Permission
from portal_api.modules.written import linked, review
from portal_api.modules.written.models import WrittenAttempt, WrittenForm
from portal_api.modules.written.router import pages_out
from portal_api.modules.written.schemas import LinkedAttemptOut, PageOut

router = APIRouter(prefix="/v1", tags=["written marking"])
DB = Annotated[Session, Depends(get_session)]
Reviewer = Annotated[Principal, Depends(require(Permission.review_content))]
Operator = Annotated[Principal, Depends(require(Permission.operate_platform))]


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


class CaseSummary(BaseModel):
    id: uuid.UUID
    reference: str = Field(description="Short script reference; learner identity is not shown to markers")
    grade: int
    subject: str
    case_kind: Literal["initial", "recheck", "completion"]
    opened_at: datetime
    due_at: datetime | None = Field(description="Service obligation for accepted work (proposed 48 h)")
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


class StaffDraft(BaseModel):
    """PR32-02: everything a saved, unreleased draft of this case intends, restored when the workspace reopens."""

    question_status: dict[str, dict[str, Any]] = Field(
        description="Questions in this case saved as pending or unavailable, with reason and any learner action"
    )
    classifications: dict[str, dict[str, str]] = Field(description="Proposed (not applied) rescan classifications")
    evidence: dict[str, list[str]] = Field(description="Copies selected as evidence per question")


class RecheckScope(BaseModel):
    target_version: int = Field(description="The released version the learner disputes")
    positions: list[int] = Field(description="Questions the learner asked to be rechecked")
    criteria: dict[str, list[str]] = Field(description="Optional disputed criteria per question")
    reason: str
    expanded_positions: list[int] = Field(description="Questions an adjudicator added, with a recorded reason")
    can_expand: bool = Field(description="Whether you may widen the recheck (academic adjudicators only)")
    carried_forward: dict[str, int] = Field(description="Earned units kept unchanged for questions outside the scope")


class CompletionScope(BaseModel):
    positions: list[int] = Field(description="Questions still pending from the released result")
    reason: str
    carried_forward: dict[str, int] = Field(description="Earned units kept for the questions already resolved")


class RevisionOut(BaseModel):
    id: uuid.UUID
    position: int
    note: str
    created_at: datetime
    prior_page_ids: list[uuid.UUID] = Field(description="The sealed pages this clearer copy relates to")
    pages: list[PageOut] = Field(description="The clearer copy's own pages (shown beside the originals)")
    classification: Literal["READABILITY", "NEW_CONTENT", "INDETERMINATE"] | None
    class_reason: str | None
    post_cutoff: bool = Field(description="Admitted strictly after the attempt's pinned upload cutoff (RS31-03)")
    upload_cutoff_at: datetime
    cutoff_timing: Literal["before_cutoff", "at_cutoff", "after_cutoff"] = Field(
        description="When the copy was admitted relative to the cutoff; at the cutoff counts as within the window"
    )


class CaseDetail(CaseSummary):
    max_units: int
    manifest: dict[str, Any]
    questions: list[CaseQuestion]
    pages: list[PageOut]
    lease_expires_at: datetime | None
    latest: StaffScore | None
    draft: StaffDraft | None = Field(default=None, description="This case's saved draft, if the latest version is one")
    recheck: RecheckScope | None
    completion: CompletionScope | None
    revisions: list[RevisionOut] = Field(description="Learner rescans for questions in this case (W06.S2.T4)")


class DecisionIn(BaseModel):
    expected_version: int = Field(ge=0)
    awards: dict[str, dict[str, dict[str, Any]]] = Field(description='{"1": {"a1": {"units": 100, "reason": "…"}}}')
    release: bool = False
    reason: str = Field(default="", max_length=1000)
    expand_positions: list[int] = Field(
        default_factory=list, max_length=20, description="Recheck only: questions to add (academic adjudicators)"
    )
    expansion_reason: str = Field(default="", max_length=1000)
    question_status: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description='Optional per question: {"2": {"status": "pending"|"unavailable"|"scored", "reason": "…", '
        '"learner_action": "rescan"|"confirm_or_rescan"}}. Unlisted questions are scored. Pending and unavailable '
        "questions take no awards. A learner action gives the learner 7 days to act.",
    )
    classifications: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description='Per learner rescan: {"<revision id>": {"class": "READABILITY"|"NEW_CONTENT"|"INDETERMINATE", '
        '"reason": "…"}}. Required for every unclassified rescan of a question in this case before release.',
    )
    evidence: dict[str, list[str]] = Field(
        default_factory=dict,
        description='Per marked question, the READABILITY rescans used as evidence: {"2": ["<revision id>"]}. '
        "Unnamed questions were marked from the sealed original.",
    )


class CriterionResult(BaseModel):
    id: str
    subpart_id: str | None
    description: str
    earned_units: int
    max_units: int
    reason: str


class LearnerRevision(BaseModel):
    id: uuid.UUID
    created_at: datetime
    classification: Literal["READABILITY", "NEW_CONTENT", "INDETERMINATE"] | None


class QuestionResult(BaseModel):
    position: int
    max_units: int
    status: Literal["scored", "pending", "unavailable"]
    status_reason: str = Field(description="Why a question is pending or unavailable")
    learner_action: Literal["rescan", "confirm_or_rescan"] | None = Field(
        default=None, description="What the teacher asked you to do for this pending question"
    )
    action_deadline: datetime | None = None
    revisions: list[LearnerRevision] = Field(default_factory=list, description="Clearer copies you sent")
    earned_units: int | None = Field(description="Null unless scored; no mark is invented for unassessed work")
    criteria: list[CriterionResult]


class RecheckOut(BaseModel):
    status: Literal["unavailable", "available", "requested", "closed"]
    window_ends_at: datetime | None = Field(description="14 days after the disputed result was released")
    reason: str | None
    eligible_positions: list[int] = Field(description="Questions that can be disputed now (when available)")
    positions: list[int] = Field(description="Questions in the open request (when requested)")
    target_version: int | None = Field(description="The released version a request targets")
    closed_reason: Literal["window_ended", "already_rechecked", "no_corrected_questions", "nothing_scored"] | None
    windows: dict[str, datetime] = Field(
        default_factory=dict, description="Per eligible question: when its appeal window ends (OCT8-04)"
    )


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
    completeness: Literal["complete", "partial_pending", "partial_unavailable"] | None = Field(
        description="Not complete means no final total: some questions are pending or could not be assessed"
    )
    scored_max_units: int | None = Field(description="Maximum of the questions that were scored")
    questions: list[QuestionResult]
    recheck: RecheckOut
    history: list[HistoryEntry] = Field(
        description="Every released version, oldest first; corrections never erase history"
    )
    linked_attempts: list[LinkedAttemptOut] = Field(
        default_factory=list,
        description="New practice tests linked to this one (W04.S3.T3); they never change this result",
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
        "due_at": case.due_at,
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


def _draft(sv: review.WrittenScoreVersion | None, case: review.WrittenReviewCase) -> StaffDraft | None:
    if sv is None or sv.released or sv.case_id != case.id:
        return None
    scope = {str(p) for p in case.positions} if case.positions else None
    intent = sv.draft_intent or {}
    return StaffDraft(
        question_status={
            p: {k: v for k, v in st.items() if k in ("status", "reason", "learner_action")}
            for p, st in (sv.question_status or {}).items()
            if (scope is None or p in scope) and st.get("status") != "scored"
        },
        classifications=intent.get("classifications", {}),
        evidence=intent.get("evidence", {}),
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
        draft=_draft(review.latest(db, case.attempt_id), case),
        recheck=_recheck_scope(db, ctx["recheck"], case, who),
        completion=_completion_scope(db, case),
        revisions=_revisions(db, case.attempt_id, {int(p) for p in (case.positions or [])} if case.positions else None),
    )


def _revisions(db: Session, attempt_id: uuid.UUID, positions: set[int] | None) -> list[RevisionOut]:
    from sqlalchemy import select as sa_select

    from portal_api.modules.written import rescans
    from portal_api.modules.written.models import WrittenPage

    out = []
    attempt = db.get(WrittenAttempt, attempt_id)
    assert attempt is not None
    cutoff = attempt.upload_cutoff_at
    for r in rescans.revisions_for(db, attempt_id, positions):
        pages = list(db.scalars(sa_select(WrittenPage).where(WrittenPage.file_id == r.file_id)))
        timing = "after_cutoff" if r.post_cutoff else "at_cutoff" if r.created_at == cutoff else "before_cutoff"
        out.append(
            RevisionOut(
                id=r.id,
                position=r.position,
                note=r.note,
                created_at=r.created_at,
                prior_page_ids=[uuid.UUID(p) for p in r.prior_page_ids],
                pages=pages_out(db, pages),
                classification=r.classification,  # type: ignore[arg-type]
                class_reason=r.class_reason,
                post_cutoff=r.post_cutoff,
                upload_cutoff_at=cutoff,
                cutoff_timing=timing,  # type: ignore[arg-type]
            )
        )
    return out


def _completion_scope(db: Session, case: review.WrittenReviewCase) -> CompletionScope | None:
    if case.case_kind != "completion":
        return None
    current = review.released_result(db, case.attempt_id)
    scope = {str(p) for p in (case.positions or [])}
    return CompletionScope(
        positions=case.positions or [],
        reason=case.reason or "",
        carried_forward={p: u for p, u in (current.question_units if current else {}).items() if p not in scope},
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
        question_status=body.question_status,
        classifications=body.classifications,
        evidence=body.evidence,
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
            completeness=None,
            scored_max_units=None,
            questions=[],
            recheck=RecheckOut(**review.recheck_state(db, attempt.id)),
            history=[],
            linked_attempts=[LinkedAttemptOut(**x) for x in linked.linked_attempts(db, attempt.id)],
        )
    ctx_questions = {str(fi.position): fi for fi in form.items}
    from portal_api.modules.written import rescans

    revisions_by_pos: dict[int, list[Any]] = {}
    for r in rescans.revisions_for(db, attempt.id):
        revisions_by_pos.setdefault(r.position, []).append(r)
    questions = []
    for pos, fi in sorted(ctx_questions.items(), key=lambda kv: int(kv[0])):
        rv = db.get(ContentVersion, fi.rubric_version_id)
        assert rv is not None
        rubric, _ = wq.parse_rubric(rv.body)
        assert rubric is not None
        given = sv.awards.get(pos, {})
        st = (sv.question_status or {}).get(pos, {"status": "scored", "reason": ""})
        scored = st["status"] == "scored"
        req = rescans.effective_request(db, attempt.id, fi.position, st)  # PR32-01: same source as admission/expiry
        questions.append(
            QuestionResult(
                position=fi.position,
                max_units=fi.max_units,
                status=st["status"],
                status_reason=st.get("reason", ""),
                learner_action=req[0] if req else None,  # type: ignore[arg-type]
                action_deadline=req[1] if req else None,
                revisions=[
                    LearnerRevision(id=r.id, created_at=r.created_at, classification=r.classification)
                    for r in revisions_by_pos.get(fi.position, [])
                ],
                earned_units=sv.question_units.get(pos, 0) if scored else None,
                criteria=[]
                if not scored
                else [
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
        completeness=sv.completeness,  # type: ignore[arg-type]
        scored_max_units=sv.scored_max_units if sv.scored_max_units is not None else sv.max_units,
        questions=questions,
        recheck=RecheckOut(**review.recheck_state(db, attempt.id)),
        history=history,
        linked_attempts=[LinkedAttemptOut(**x) for x in linked.linked_attempts(db, attempt.id)],
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


# ------------------------------------------------------------------ operations (R05: funded capacity, obligations)
class CapacityIn(BaseModel):
    max_open_cases: int = Field(ge=0, le=100_000, description="0 stops new written starts in this scope")
    reason: str = Field(min_length=5, max_length=1000)


class BacklogRow(BaseModel):
    grade: int
    subject: str
    max_open_cases: int
    open_cases: int
    open_permits: int = Field(description="Started, unsubmitted written tests that may still become cases")
    accepting: bool
    overdue_cases: int = Field(description="Queued cases past their due time (service obligation missed)")


@router.put(
    "/ops/written-capacity/{grade}/{subject}",
    response_model=BacklogRow,
    summary="Set funded teacher-review capacity for a class and subject (operators, MFA, audited)",
)
def set_capacity(db: DB, who: Operator, grade: int, subject: str, body: CapacityIn, response: Response) -> BacklogRow:
    _private(response)
    if grade not in (11, 12):
        raise NotFound("Unknown class.")
    review.set_capacity(db, who, grade, subject, body.max_open_cases, body.reason)
    return _backlog_row(db, grade, subject)


def _backlog_row(db: Session, grade: int, subject: str) -> BacklogRow:
    from sqlalchemy import func, select

    cap = review.capacity_state(db, grade, subject)
    overdue = db.scalar(
        select(func.count())
        .select_from(review.WrittenReviewCase)
        .where(
            review.WrittenReviewCase.status == "queued",
            review.WrittenReviewCase.grade_number == grade,
            review.WrittenReviewCase.subject_code == subject,
            review.WrittenReviewCase.due_at < func.now(),
        )
    )
    return BacklogRow(
        grade=grade,
        subject=subject,
        max_open_cases=cap["max_open_cases"],
        open_cases=cap["open_cases"],
        open_permits=cap["open_permits"],
        accepting=cap["accepting"],
        overdue_cases=int(overdue or 0),
    )


@router.get(
    "/ops/written-backlog", response_model=list[BacklogRow], summary="Review capacity, backlog and overdue work"
)
def backlog(db: DB, who: Operator, response: Response) -> list[BacklogRow]:
    _private(response)
    from sqlalchemy import select, union

    scopes = db.execute(
        union(
            select(review.ReviewCapacity.grade_number, review.ReviewCapacity.subject_code),
            select(review.WrittenReviewCase.grade_number, review.WrittenReviewCase.subject_code).where(
                review.WrittenReviewCase.status == "queued"
            ),
        )
    ).all()
    return [_backlog_row(db, g, s) for g, s in sorted(scopes)]


class RebaseIn(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)


@router.post(
    "/studio/written/cases/{case_id}/rebase",
    response_model=CaseDetail,
    summary="Rebase an open recheck onto the current result (academic adjudicators; audited)",
)
def rebase(db: DB, who: Reviewer, case_id: uuid.UUID, body: RebaseIn, response: Response) -> CaseDetail:
    _private(response)
    return _detail(db, review.rebase_recheck(db, who, case_id, body.reason), who)


@router.get(
    "/studio/written/cases/{case_id}/pages/{page_id}/detail",
    summary="Higher-detail rendition of a submitted page, or a region of it (markers in scope; private)",
)
def case_page_detail(
    db: DB,
    who: Reviewer,
    case_id: uuid.UUID,
    page_id: uuid.UUID,
    region: Annotated[
        str | None, Query(pattern=r"^[0-9.]+,[0-9.]+,[0-9.]+,[0-9.]+$", description="x,y,w,h as page fractions")
    ] = None,
) -> Response:
    box = tuple(float(v) for v in region.split(",")) if region else None
    png, provenance = review.staff_page_detail(db, who, case_id, page_id, box)  # type: ignore[arg-type]
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", **provenance},
    )


# ------------------------------------------------------------------ learner actions on pending questions (W06.S2.T4)
RESCAN_LIMIT = 15 * 1024 * 1024


@router.post(
    "/written-attempts/{attempt_id}/questions/{position}/rescan",
    status_code=201,
    summary="Send a clearer copy of one pending answer (raw JPEG/PNG/PDF body; kept beside the sealed original)",
)
async def rescan(
    db: DB,
    who: CurrentPrincipal,
    attempt_id: uuid.UUID,
    position: int,
    request: Request,
    response: Response,
    note: Annotated[str, Query(max_length=500)] = "",
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", min_length=8, max_length=80)] = None,
) -> dict[str, Any]:
    from starlette.concurrency import run_in_threadpool

    from portal_api.errors import TooLarge
    from portal_api.modules.written import rescans

    _private(response)
    buf = bytearray()
    async for chunk in request.stream():
        buf.extend(chunk)
        if len(buf) > RESCAN_LIMIT:
            raise TooLarge("This file is larger than any accepted page.")
    if not idempotency_key:
        from portal_api.errors import Unprocessable

        raise Unprocessable(
            "Send an Idempotency-Key so a retry can't create a second copy.", code_reason="KEY_REQUIRED"
        )
    rev, replay = await run_in_threadpool(
        rescans.submit_rescan, db, who, attempt_id, position, bytes(buf), note, idempotency_key
    )
    if replay:
        response.status_code = 200  # already accepted: the original acknowledgement, nothing new created
    return {
        "id": str(rev.id),
        "position": rev.position,
        "created_at": rev.created_at.isoformat(),
        "post_cutoff": rev.post_cutoff,
        "replay": replay,
    }


@router.post(
    "/written-attempts/{attempt_id}/questions/{position}/confirm-unanswered",
    status_code=204,
    summary="Confirm you didn't answer a question the teacher found blank (resolved as unanswered; allowance returned)",
)
def confirm_unanswered(db: DB, who: CurrentPrincipal, attempt_id: uuid.UUID, position: int) -> Response:
    from portal_api.modules.written import rescans

    rescans.confirm_unanswered(db, who, attempt_id, position)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})
