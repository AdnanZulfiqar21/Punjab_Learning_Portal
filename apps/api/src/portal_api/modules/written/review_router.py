"""Teacher marking API (W06.S1) and the learner's released result (W07.S1.T1)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from portal_api.db import get_session
from portal_api.errors import NotFound
from portal_api.modules.assessment.schemas import RelatedLesson
from portal_api.modules.content import written as wq
from portal_api.modules.content.models import ContentVersion
from portal_api.modules.identity.deps import CurrentPrincipal, Principal, require
from portal_api.modules.identity.permissions import Permission
from portal_api.modules.written import linked, review
from portal_api.modules.written.models import WrittenAttempt, WrittenForm
from portal_api.modules.written.router import pages_out
from portal_api.modules.written.schemas import LinkedAttemptOut, PageOut

log = logging.getLogger("portal_api.written")
router = APIRouter(prefix="/v1", tags=["written marking"])
DB = Annotated[Session, Depends(get_session)]
Reviewer = Annotated[Principal, Depends(require(Permission.review_content))]
Operator = Annotated[Principal, Depends(require(Permission.operate_platform))]
# NEW-11: rebasing a recheck is an adjudication: the adjudicate permission with an MFA session (MFA_REQUIRED).
RebaseAdjudicator = Annotated[Principal, Depends(require(Permission.adjudicate))]


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


class CaseSummary(BaseModel):
    id: uuid.UUID
    reference: str = Field(description="Short script reference; learner identity is not shown to markers")
    grade: int
    subject: str
    case_kind: Literal["initial", "recheck", "completion", "regrade"]
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
    regrade: CompletionScope | None = Field(
        default=None, description="Regrade cases: the questions a rubric correction changed, and why (W06.S2.T3)"
    )
    revisions: list[RevisionOut] = Field(description="Learner rescans for questions in this case (W06.S2.T4)")


class DecisionIn(BaseModel):
    expected_version: int = Field(ge=0)
    awards: dict[str, dict[str, dict[str, Any]]] = Field(
        description='{"1": {"a1": {"units": 100, "reason": "…", '
        '"evidence": [{"page_id": "…", "region": [x, y, w, h]}]}}}'
        "; evidence is optional: pages this question was mapped to, each with an optional region of its preview."
    )
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


class EvidenceLinkOut(BaseModel):
    """W07.S1.T2 (FEEDBACK-EVIDENCE-01): where on your script a criterion's feedback points."""

    page_id: uuid.UUID
    page_number: int = Field(description="The page's number as you uploaded it")
    region: list[float] | None = Field(description="x, y, width, height as fractions of the upright page; null = whole")
    where: str = Field(description='Plain words for the place, e.g. "page 2, top left"')
    available: bool = Field(description="False once the scan is no longer available: nothing is highlighted then")


class CriterionResult(BaseModel):
    id: str
    subpart_id: str | None
    description: str
    earned_units: int
    max_units: int
    reason: str
    evidence: list[EvidenceLinkOut] = Field(default_factory=list)


MAX_FOCUS = 5


def _next_steps(rubric: Any, given: dict[str, Any], lessons: list[Any], chapter_id: uuid.UUID | None) -> NextStepsOut:
    """Criteria that didn't earn full credit, with the rubric's own words, and the topic's live lessons. An
    alternative route the learner didn't take is left out once another route in its group earned credit."""
    earned = {c.id: int(given.get(c.id, {}).get("units", 0)) for c in rubric.criteria}
    credited = {(c.subpart_id, c.alternative_group) for c in rubric.criteria if c.alternative_group and earned[c.id]}
    focus = [
        FocusOut(criterion_id=c.id, description=c.description, common_mistakes=list(c.misconceptions))
        for c in rubric.criteria
        if c.description
        and earned[c.id] < c.max_units
        and not (c.alternative_group and not earned[c.id] and (c.subpart_id, c.alternative_group) in credited)
    ][:MAX_FOCUS]
    return NextStepsOut(
        focus=focus,
        lessons=[RelatedLesson(id=lesson.id, title=lesson.title, chapter_id=lesson.chapter_id) for lesson in lessons],
        lessons_missing=not lessons,
        chapter_id=chapter_id,
    )


def _where(number: int, region: list[float] | None) -> str:
    if not region:
        return f"page {number}"
    x, y, w, h = region
    cx, cy = x + w / 2, y + h / 2
    v = "top" if cy < 1 / 3 else "bottom" if cy > 2 / 3 else "middle"
    hz = "left" if cx < 1 / 3 else "right" if cx > 2 / 3 else "centre"
    return f"page {number}, " + ("centre" if (v, hz) == ("middle", "centre") else f"{v} {hz}")


def _evidence_links(db: Session, attempt_id: uuid.UUID, raw: object) -> list[EvidenceLinkOut]:
    """Only grounded places: a page of this attempt with its preview still stored. Anything else is shown as no
    longer available, and never with an invented highlight."""
    from portal_api.modules.written import service, storage

    pages = {str(p.id): (n, p) for n, p in enumerate(service._pages(db, attempt_id), start=1)}
    store = storage.get_store()
    out = []
    for a in review.anchors(raw):
        n, page = pages.get(a["page_id"], (0, None))
        if n == 0:
            continue  # not a page of this attempt: never shown
        live = page is not None and bool(page.preview_key) and store.exists(page.preview_key or "")
        region = a["region"] if live else None
        out.append(
            EvidenceLinkOut(
                page_id=uuid.UUID(a["page_id"]),
                page_number=n,
                region=region,
                where=_where(n, a["region"]),
                available=live,
            )
        )
    return out


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
    model_answer: list[dict[str, Any]] | None = Field(
        default=None,
        description="The reviewed worked answer from the marking guide that marked this question; only once scored",
    )
    model_answer_note: str | None = Field(
        default=None, description="Set when a correction to the marking guide affects the worked answer"
    )
    academic_review: Literal["open", "resolved"] | None = Field(
        default=None,
        description="open: a senior subject reviewer is deciding how the marking guide applies (no mark until then)",
    )
    revisions: list[LearnerRevision] = Field(default_factory=list, description="Clearer copies you sent")
    earned_units: int | None = Field(description="Null unless scored; no mark is invented for unassessed work")
    criteria: list[CriterionResult]
    next_steps: NextStepsOut | None = Field(default=None, description="Only for a scored question that lost marks")


class FocusOut(BaseModel):
    criterion_id: str
    description: str = Field(description="What the rubric asks for, in its own approved words")
    common_mistakes: list[str] = Field(description="The rubric's listed misconceptions for this criterion")


class NextStepsOut(BaseModel):
    """W07.S2.T1 (NEXT-STEPS-01): where to go next on a question that lost marks. Everything here is approved content:
    the rubric's own wording for what was missed and live lessons for the question's topic. Nothing is generated."""

    focus: list[FocusOut]
    lessons: list[RelatedLesson]
    lessons_missing: bool = Field(description="True when no reviewed lesson is published for this topic or chapter")
    chapter_id: uuid.UUID | None = Field(description="The question's chapter (its outline and textbook pages)")


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


# COMPLETENESS-01 (§20.9.3). Apps released before it know only the first three values (MIGRATION-COMPAT-01), so the
# legacy `completeness` field keeps them and the full state is a separate field.
AssessmentState = Literal["complete", "partial_pending", "partial_unavailable", "unavailable"]
LegacyCompleteness = Literal["complete", "partial_pending", "partial_unavailable"]
WorkStatus = review.WorkStatus


def legacy_completeness(state: str | None) -> LegacyCompleteness | None:
    """What an older app is told: a paper where nothing could be assessed is a partial result with no marked
    questions there, which it already shows as "Some questions couldn't be assessed", with no total."""
    if state is None:
        return None
    return "partial_unavailable" if state == "unavailable" else state  # type: ignore[return-value]


VersionLabel = Literal["recheck", "clearer_copy", "marking_guide_corrected", "pending_completed", "deadline_passed"]


class VersionQuestionOut(BaseModel):
    """W07.S2.T2 (HISTORY-01): one question as a released version recorded it."""

    position: int
    status: Literal["scored", "pending", "unavailable"]
    earned_units: int | None = Field(description="Null unless scored")
    rubric_version: int | None = Field(description="The marking-guide version it was marked under (null if unmarked)")
    evidence: Literal["original", "clearer_copy"] = Field(
        description="Marked from the submitted original, or from a clearer copy the learner sent"
    )
    changed: bool = Field(description="True when its status or mark differs from the previous version")
    reason: str | None = Field(
        description="Why this version touched it, in plain words; null when it was simply carried forward"
    )


class ScoreVersionOut(BaseModel):
    version: int
    total_units: int | None = Field(description="None when nothing could be assessed: that version has no mark")
    assessment_state: AssessmentState
    case_kind: str
    decision_method: Literal["TEACHER", "SYSTEM", "LEARNER"] = Field(
        description="TEACHER: a teacher decided; SYSTEM: a deadline or an unchanged carry-forward; LEARNER: confirmed"
    )
    labels: list[VersionLabel] = Field(
        description="What kind of change this version is: a recheck, marking from a clearer copy, a marking-guide "
        "correction, pending questions completed, or a deadline that passed"
    )
    questions: list[VersionQuestionOut]
    released_at: datetime


class RecheckIn(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)
    positions: list[int] = Field(min_length=1, max_length=20)
    criteria: dict[str, list[str]] = Field(
        default_factory=dict, description="Optional: disputed criterion ids per question position"
    )


class NoticeOut(BaseModel):
    kind: str
    positions: list[int]
    message: str
    created_at: datetime


class WrittenResultOut(BaseModel):
    status: Literal["pending", "released"]
    version: int | None
    total_units: int | None
    max_units: int
    released_at: datetime | None
    decision_method: str | None
    completeness: LegacyCompleteness | None = Field(
        description="Not complete means no final total: some questions are pending or could not be assessed. Kept "
        "for older apps: a paper where nothing could be assessed is partial_unavailable here; read assessment_state"
    )
    assessment_state: AssessmentState | None = Field(
        description="complete; partial_pending (some questions are still being marked); partial_unavailable (some "
        "could not be assessed); unavailable (none could be assessed, so this test has no mark). None until released"
    )
    scored_max_units: int | None = Field(description="Maximum of the questions that were scored")
    pending_max_units: int | None = Field(
        default=None,
        description="Maximum of the questions still being marked (P). Scored (S), pending (P) and "
        "could-not-be-assessed (U) maxima always add up to max_units (M), §20.9.3. None until released",
    )
    unavailable_max_units: int | None = Field(
        default=None, description="Maximum of the questions that could not be assessed (U). None until released"
    )
    assessment_method: Literal["teacher", "none"] | None = Field(
        default=None,
        description="Who assessed the scored questions only (S): teacher, or none when nothing was scored. It never "
        "describes the whole paper while questions are pending or could not be assessed. None until released",
    )
    work_status: WorkStatus | None = Field(
        default=None,
        description="What is happening to the script now, apart from its marks: in_review (a teacher has it or will), "
        "action_required (you were asked for a clearer copy or a confirmation), delayed (marking is past the time "
        "promised), finished. None before the script is submitted",
    )
    questions: list[QuestionResult]
    recheck: RecheckOut
    history: list[HistoryEntry] = Field(
        description="Released versions that have a mark, oldest first (kept for older apps; a version where nothing "
        "could be assessed is listed only in versions)"
    )
    versions: list[ScoreVersionOut] = Field(
        description="Every released version, oldest first, including any with no mark; corrections never erase history"
    )
    notices: list[NoticeOut] = Field(
        default_factory=list, description="Changes to this result's basis, such as a marking-guide correction"
    )
    awaiting_regrade: list[int] = Field(
        default_factory=list,
        description="Questions a teacher will re-mark under a corrected marking guide (current marks stand until then)",
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
        regrade=_completion_scope(db, case, kind="regrade"),
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
        # The stored flag is authoritative for "after"; at-or-before is split only for display.
        timing = "after_cutoff" if r.post_cutoff else "at_cutoff" if r.created_at >= cutoff else "before_cutoff"
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


def _completion_scope(db: Session, case: review.WrittenReviewCase, kind: str = "completion") -> CompletionScope | None:
    if case.case_kind != kind:
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
        can_expand=review.can_adjudicate(db, who, case) and who.claims.mfa,
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
            assessment_state=None,
            scored_max_units=None,
            work_status=review.work_status(db, attempt.id, pending=True, action_required=False)
            if attempt.status == "sealed"
            else None,
            questions=[],
            recheck=RecheckOut(**review.recheck_state(db, attempt.id)),
            history=[],
            versions=[],
            notices=_notices(db, attempt.id),
            awaiting_regrade=_awaiting_regrade(db, attempt.id),
            linked_attempts=[LinkedAttemptOut(**x) for x in linked.linked_attempts(db, attempt.id)],
        )
    ctx_questions = {str(fi.position): fi for fi in form.items}
    from portal_api.modules.content.models import ContentItem
    from portal_api.modules.content.related import live_lessons_for
    from portal_api.modules.written import rescans

    question_items = {}
    for pos, fi in ctx_questions.items():
        qv = db.get(ContentVersion, fi.question_version_id)
        item = db.get(ContentItem, qv.item_id) if qv is not None else None
        if item is not None:
            question_items[pos] = item
    lessons = live_lessons_for(db, question_items)

    revisions_by_pos: dict[int, list[Any]] = {}
    for r in rescans.revisions_for(db, attempt.id):
        revisions_by_pos.setdefault(r.position, []).append(r)
    reviews = _academic_states(db, attempt.id)  # ACADEMIC-REVIEW-01
    awaiting = set(_awaiting_regrade(db, attempt.id))
    questions = []
    for pos, fi in sorted(ctx_questions.items(), key=lambda kv: int(kv[0])):
        rv = db.get(ContentVersion, uuid.UUID(str(sv.rubric_version_ids.get(pos, fi.rubric_version_id))))
        assert rv is not None
        rubric, _ = wq.parse_rubric(rv.body, stored=True)
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
                academic_review=reviews.get(fi.position),  # type: ignore[arg-type]
                # MODEL-ANSWER-01: released with the mark, from the guide version that marked it; never before.
                model_answer=list(rv.body.get("model_answer") or []) or None if scored else None,
                model_answer_note=_model_answer_note(sv, pos, fi.position in awaiting)
                if scored and rubric.model_answer
                else None,
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
                        evidence=_evidence_links(db, attempt.id, given.get(c.id, {}).get("evidence")),
                    )
                    for c in rubric.criteria
                ],
                next_steps=_next_steps(
                    rubric, given, lessons.get(pos, []), q.chapter_id if (q := question_items.get(pos)) else None
                )
                if scored and sv.question_units.get(pos, 0) < fi.max_units
                else None,
            )
        )
    versions = _version_history(db, review.released_history(db, attempt.id))
    history = [  # older apps always print a number, so a version with no mark is left out rather than shown as 0
        HistoryEntry(version=v.version, total_units=v.total_units, case_kind=v.case_kind, released_at=v.released_at)
        for v in versions
        if v.total_units is not None
    ]
    # RESULT-ARITHMETIC-01 (§20.9.3, W07.S1.T1): S + P + U = M, from the same per-question states the learner sees.
    by_status = {s: sum(q.max_units for q in questions if q.status == s) for s in ("scored", "pending", "unavailable")}
    if sum(by_status.values()) != sv.max_units:
        log.error(
            "written result %s v%s: scored %s + pending %s + unavailable %s != maximum %s",
            attempt.id,
            sv.version,
            by_status["scored"],
            by_status["pending"],
            by_status["unavailable"],
            sv.max_units,
        )
    return WrittenResultOut(
        status="released",
        version=sv.version,
        total_units=None if sv.completeness == "unavailable" else sv.total_units,
        max_units=sv.max_units,
        released_at=sv.created_at,
        decision_method=sv.decision_method,
        completeness=legacy_completeness(sv.completeness),
        assessment_state=sv.completeness,  # type: ignore[arg-type]
        scored_max_units=sv.scored_max_units if sv.scored_max_units is not None else sv.max_units,
        pending_max_units=by_status["pending"],
        unavailable_max_units=by_status["unavailable"],
        # R0: every scored question was marked by a teacher (a carried-forward regrade keeps the teacher's marks).
        assessment_method="teacher" if any(q.status == "scored" for q in questions) else "none",
        work_status=review.work_status(
            db,
            attempt.id,
            pending=any(q.status == "pending" for q in questions),
            action_required=any(q.learner_action for q in questions),
        ),
        questions=questions,
        recheck=RecheckOut(**review.recheck_state(db, attempt.id)),
        history=history,
        versions=versions,
        notices=_notices(db, attempt.id),
        awaiting_regrade=_awaiting_regrade(db, attempt.id),
        linked_attempts=[LinkedAttemptOut(**x) for x in linked.linked_attempts(db, attempt.id)],
    )


def _q_status(sv: review.WrittenScoreVersion, pos: str) -> str:
    return str((sv.question_status or {}).get(pos, {}).get("status", "scored"))


def _scope(db: Session, case: review.WrittenReviewCase | None) -> set[int] | None:
    """The questions a case decided (None: all of them). A recheck covers the learner's questions plus any an
    adjudicator added; a completion or regrade case names its own."""
    if case is None or case.case_kind == "initial":
        return None
    request = review.recheck_request(db, case)
    if request is not None:
        return {*request.positions, *(request.expanded_positions or [])}
    return set(case.positions) if case.positions else None


def _q_reason(
    sv: review.WrittenScoreVersion, scope: set[int] | None, before: tuple[str, int | None], now: VersionQuestionOut
) -> str | None:
    """HISTORY-01: a plain explanation for a question this version decided (None when it was only carried forward)."""
    in_scope = scope is None or now.position in scope
    if not now.changed and not in_scope:
        return None
    if sv.version == 1:
        return None  # the first marking needs no explanation
    if now.status == "unavailable" and before[0] == "pending" and sv.decision_method == "SYSTEM":
        return (
            "No clearer copy arrived by the deadline, so this question couldn't be assessed; "
            "its allowance was returned."
        )
    if now.status == "unavailable":
        return "A teacher found that this question couldn't be assessed; its allowance was returned."
    copy = " from the clearer copy you sent" if now.evidence == "clearer_copy" else ""
    if before[0] == "pending" and now.status == "scored":
        return f"Marked{copy} after it was pending."
    if sv.case_kind == "recheck":
        if now.changed:
            return f"Marked again{copy} by a different teacher after your recheck request."
        return "Checked again by a different teacher after your recheck request; the mark stands."
    if sv.case_kind == "regrade":
        if sv.decision_method == "SYSTEM":
            return "Unchanged after a marking-guide correction." if not now.changed else None
        return f"Marked again{copy} under the corrected marking guide."
    if now.changed:
        return f"Changed by a teacher{copy}."
    return None


def _version_history(db: Session, rows: list[review.WrittenScoreVersion]) -> list[ScoreVersionOut]:
    """W07.S2.T2 (HISTORY-01): every released version with, per question, its mark, the marking-guide version and
    evidence it used, and why it changed. Corrections never erase a version (COMPLETENESS-01: no-mark versions have
    a null total)."""
    from sqlalchemy import select as sa_select

    rubric_ids = {uuid.UUID(v) for sv in rows for v in (sv.rubric_version_ids or {}).values() if v}
    numbers: dict[uuid.UUID, int] = {}
    if rubric_ids:
        query = sa_select(ContentVersion.id, ContentVersion.number).where(ContentVersion.id.in_(rubric_ids))
        numbers = {vid: int(n) for vid, n in db.execute(query)}
    out: list[ScoreVersionOut] = []
    previous: review.WrittenScoreVersion | None = None
    for sv in rows:
        scope = _scope(db, db.get(review.WrittenReviewCase, sv.case_id))
        positions = sorted(
            {*map(str, (sv.rubric_version_ids or {})), *(sv.question_status or {}), *(sv.question_units or {})}, key=int
        )
        questions: list[VersionQuestionOut] = []
        for pos in positions:
            status = _q_status(sv, pos)
            earned = int(sv.question_units[pos]) if status == "scored" and pos in (sv.question_units or {}) else None
            before = (
                (
                    _q_status(previous, pos),
                    (previous.question_units or {}).get(pos) if _q_status(previous, pos) == "scored" else None,
                )
                if previous is not None
                else ("", None)
            )
            rid = (sv.rubric_version_ids or {}).get(pos)
            q = VersionQuestionOut(
                position=int(pos),
                status=status,  # type: ignore[arg-type]
                earned_units=earned,
                rubric_version=numbers.get(uuid.UUID(rid)) if rid and status == "scored" else None,
                evidence="clearer_copy" if (sv.evidence_revisions or {}).get(pos) else "original",
                changed=previous is not None and (before[0], before[1]) != (status, earned),
                reason=None,
            )
            q.reason = _q_reason(sv, scope, before, q)
            questions.append(q)
        labels: list[VersionLabel] = []
        if sv.case_kind == "recheck":
            labels.append("recheck")
        if sv.case_kind == "regrade":
            labels.append("marking_guide_corrected")
        if sv.case_kind == "completion" and any(q.reason and "after it was pending" in q.reason for q in questions):
            labels.append("pending_completed")
        if sv.decision_method == "SYSTEM" and any(q.reason and "deadline" in q.reason for q in questions):
            labels.append("deadline_passed")
        newly_copied = {
            p
            for p, e in (sv.evidence_revisions or {}).items()
            if e and (previous is None or (previous.evidence_revisions or {}).get(p) != e)
        }
        if newly_copied:
            labels.append("clearer_copy")
        out.append(
            ScoreVersionOut(
                version=sv.version,
                total_units=None if sv.completeness == "unavailable" else sv.total_units,
                assessment_state=sv.completeness or "complete",  # type: ignore[arg-type]
                case_kind=sv.case_kind,
                decision_method=sv.decision_method,  # type: ignore[arg-type]
                labels=labels,
                questions=questions,
                released_at=sv.created_at,
            )
        )
        previous = sv
    return out


def _model_answer_note(sv: Any, pos: str, regrade_pending: bool) -> str | None:
    """MODEL-ANSWER-01: say when an academic correction affects the worked answer shown."""
    if regrade_pending:
        return (
            "A correction to the marking guide is waiting to be applied to your answer; this worked answer may change."
        )
    if (sv.effective_adjudication or {}).get(pos):
        return "This worked answer is from the corrected marking guide your answer was marked under."
    return None


def _academic_states(db: Session, attempt_id: uuid.UUID) -> dict[int, str]:
    """Per question, the latest academic review's status (open wins over earlier resolved ones)."""
    from sqlalchemy import select as sa_select

    from portal_api.modules.written.academic import AcademicReview

    out: dict[int, str] = {}
    for r in db.scalars(
        sa_select(AcademicReview).where(AcademicReview.attempt_id == attempt_id).order_by(AcademicReview.raised_at)
    ):
        out[r.position] = "open" if r.status == "open" or out.get(r.position) == "open" else r.status
    return out


def _awaiting_regrade(db: Session, attempt_id: uuid.UUID) -> list[int]:
    from sqlalchemy import select as sa_select

    rows = db.scalars(
        sa_select(review.WrittenReviewCase.positions).where(
            review.WrittenReviewCase.attempt_id == attempt_id,
            review.WrittenReviewCase.case_kind == "regrade",
            review.WrittenReviewCase.status == "queued",
        )
    )
    return sorted({p for ps in rows for p in (ps or [])})


def _notices(db: Session, attempt_id: uuid.UUID) -> list[NoticeOut]:
    from portal_api.modules.written import adjudication

    return [
        NoticeOut(kind=n.kind, positions=n.positions, message=n.message, created_at=n.created_at)
        for n in adjudication.notices(db, attempt_id)
    ]


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
class StaffingIn(BaseModel):
    """W06.S3.T2 (STAFFING-01): the staffing behind a scope's capacity."""

    reviewer_hours_per_week: int = Field(ge=1, le=10_000, description="Productive marking hours a week in this scope")
    fixed_hours_per_week: int = Field(ge=0, le=10_000, description="Calibration, adjudication, training and meetings")
    minutes_per_script: int = Field(ge=1, le=600, description="Teacher minutes to mark one script")
    turnaround_days: int = Field(ge=1, le=60, description="The turnaround learners are promised")

    @model_validator(mode="after")
    def _fits(self) -> StaffingIn:
        if self.fixed_hours_per_week > self.reviewer_hours_per_week:
            raise ValueError("fixed obligations can't exceed the productive hours")
        return self


class CapacityIn(BaseModel):
    max_open_cases: int = Field(ge=0, le=100_000, description="0 stops new written starts in this scope")
    reason: str = Field(min_length=5, max_length=1000)
    staffing: StaffingIn | None = Field(default=None, description="Leave out to keep the current staffing")
    clear_staffing: bool = Field(
        default=False, description="Remove the staffing figures (the case limit alone applies)"
    )


class StaffingOut(BaseModel):
    reviewer_hours_per_week: int
    fixed_hours_per_week: int
    minutes_per_script: int
    turnaround_days: int
    available_minutes: int = Field(description="Productive minutes left after fixed obligations, over the turnaround")
    due_minutes: int = Field(description="Minutes already owed to queued cases and started tests")
    admissible_scripts: int = Field(description="New scripts that still fit within the turnaround")
    turnaround_estimate_days: int | None = Field(description="How long a script started now would wait")


class DemandOut(BaseModel):
    """W06.S3.T1 (DEMAND-01): measured review demand (roadmap §20.13.3). A forecast only: admission is unchanged."""

    released_scripts: int = Field(description="First markings released in the last 90 days")
    rechecks: int = Field(description="Recheck cases opened in the last 90 days")
    recheck_rate: float | None = Field(description="Rechecks per released script; null until 20 were released")
    recheck_window_releases: int = Field(
        description="First markings released in the last 14 days (still open to a recheck)"
    )
    expected_rechecks: int = Field(description="Rechecks still expected from those (rate x releases, rounded up)")
    queued_by_kind: dict[str, int] = Field(description="Queued cases by kind: initial, recheck, completion, regrade")
    expected_recheck_minutes: int | None = Field(description="Minutes those rechecks would take (staffing recorded)")
    admissible_if_rechecks_counted: int | None = Field(
        description="New scripts that would fit if expected rechecks were also subtracted (a WA-D08 choice)"
    )
    timed_scripts: int = Field(
        default=0, description="First markings in 90 days with a recorded start (MARKING-TIME-01)"
    )
    median_take_to_release_minutes: float | None = Field(
        default=None,
        description="Median elapsed minutes from taking a first marking to releasing it. Elapsed time with breaks "
        "included, not measured working time",
    )


class BacklogRow(BaseModel):
    grade: int
    subject: str
    max_open_cases: int
    open_cases: int
    open_permits: int = Field(description="Started, unsubmitted written tests that may still become cases")
    accepting: bool
    overdue_cases: int = Field(description="Queued cases past their due time (service obligation missed)")
    # W06.S3.T1 (QUEUE-AGEING-01): how long queued cases have waited, against the proposed 24 h / 48 h targets (§20.10).
    queued_under_24h: int = 0
    queued_24_to_48h: int = 0
    queued_over_48h: int = 0
    oldest_queued_at: datetime | None = Field(default=None, description="When the longest-waiting queued case opened")
    staffing: StaffingOut | None = None
    demand: DemandOut | None = None


@router.put(
    "/ops/written-capacity/{grade}/{subject}",
    response_model=BacklogRow,
    summary="Set funded teacher-review capacity for a class and subject (operators, MFA, audited)",
)
def set_capacity(db: DB, who: Operator, grade: int, subject: str, body: CapacityIn, response: Response) -> BacklogRow:
    _private(response)
    if grade not in (11, 12):
        raise NotFound("Unknown class.")
    staffing = {} if body.clear_staffing else body.staffing.model_dump() if body.staffing else None
    review.set_capacity(db, who, grade, subject, body.max_open_cases, body.reason, staffing)
    return _backlog_row(db, grade, subject)


def _backlog_row(db: Session, grade: int, subject: str) -> BacklogRow:
    from datetime import timedelta

    from sqlalchemy import and_, func, select

    cap = review.capacity_state(db, grade, subject)
    case = review.WrittenReviewCase
    waited = func.now() - case.opened_at
    day, two = timedelta(hours=24), timedelta(hours=48)
    young, middle, old, oldest = db.execute(
        select(
            func.count().filter(waited < day),
            func.count().filter(and_(waited >= day, waited < two)),
            func.count().filter(waited >= two),
            func.min(case.opened_at),
        ).where(case.status == "queued", case.grade_number == grade, case.subject_code == subject)
    ).one()
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
        queued_under_24h=int(young or 0),
        queued_24_to_48h=int(middle or 0),
        queued_over_48h=int(old or 0),
        oldest_queued_at=oldest,
        staffing=StaffingOut(**cap["staffing"]) if cap["staffing"] else None,
        demand=DemandOut(**review.review_demand(db, grade, subject, db.get(review.ReviewCapacity, (grade, subject)))),
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
def rebase(db: DB, who: RebaseAdjudicator, case_id: uuid.UUID, body: RebaseIn, response: Response) -> CaseDetail:
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
    original: Annotated[bool, Query(description="The untouched original, without the learner's turn or trim")] = False,
) -> Response:
    box = tuple(float(v) for v in region.split(",")) if region else None
    png, provenance = review.staff_page_detail(db, who, case_id, page_id, box, original)  # type: ignore[arg-type]
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


# ------------------------------------------------------------------ W06.S2.T3 rubric adjudications across attempts
# W06-01: every mutation needs the adjudicate permission with an MFA session (the matrix's MFA_REQUIRED); reading is
# open to scoped academic staff so markers can see why a regrade case exists.
Adjudicator = Annotated[Principal, Depends(require(Permission.adjudicate))]


class AdjudicationIn(BaseModel):
    rubric_item_id: uuid.UUID
    reason: str = Field(min_length=20, max_length=2000)
    from_version_ids: list[uuid.UUID] | None = Field(
        default=None, description="Earlier published versions to correct; default: all of them for the same question"
    )
    supersedes_ids: list[uuid.UUID] = Field(
        default_factory=list, description="Every active correction this one replaces (must match the overlap exactly)"
    )
    retain_descendant_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="Active descendants of the replaced corrections to keep (each descendant is replaced or kept)",
    )


class AdjudicationOut(BaseModel):
    id: uuid.UUID
    rubric_item_id: uuid.UUID
    grade: int
    subject: str
    from_version_ids: list[str]
    to_version_id: uuid.UUID
    reason: str
    status: Literal["active", "superseded"]
    supersedes_ids: list[str]
    retained_descendant_ids: list[str] = Field(default_factory=list)
    superseded_by_id: uuid.UUID | None
    approved_at: datetime
    compatibility: dict[str, Any] = Field(
        description="Per corrected version: criterion diff and whether human marks carry forward unchanged"
    )
    impact: dict[str, Any] | None = Field(
        default=None,
        description="total_attempts, processed, remaining, failed, unaffected, forms, released_results, "
        "evidence_revisions, applied_outcomes (detail view only; computed with bounded aggregate queries)",
    )
    latest_job: RegradeJobOut | None = None


class RegradeJobOut(BaseModel):
    id: uuid.UUID
    adjudication_id: uuid.UUID
    status: Literal["queued", "running", "succeeded", "failed", "superseded"]
    processed: int
    regraded: int
    unaffected: int
    failed: int
    remaining: int | None
    batches: int
    last_error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class AdjudicationSourcesOut(BaseModel):
    published_version_id: str | None
    published_number: int | None
    versions: list[dict[str, Any]] = Field(
        description="Earlier published versions: compatibility, denominator check, claiming corrections, scripts"
    )
    active: list[dict[str, Any]]


class RegradeAttemptsOut(BaseModel):
    total: int
    items: list[dict[str, Any]]


def _job_out(j: Any) -> RegradeJobOut:
    return RegradeJobOut(
        id=j.id,
        adjudication_id=j.adjudication_id,
        status=j.status,
        processed=j.processed,
        regraded=j.regraded,
        unaffected=j.unaffected,
        failed=j.failed,
        remaining=j.remaining,
        batches=j.batches,
        last_error=j.last_error,
        created_at=j.created_at,
        started_at=j.started_at,
        finished_at=j.finished_at,
    )


def _adj_out(db: Session, a: Any, *, detail: bool) -> AdjudicationOut:
    from sqlalchemy import select as sa_select

    from portal_api.modules.written import adjudication, regrade_jobs

    job = db.scalar(
        sa_select(regrade_jobs.RegradeJob)
        .where(regrade_jobs.RegradeJob.adjudication_id == a.id)
        .order_by(regrade_jobs.RegradeJob.created_at.desc())
        .limit(1)
    )
    return AdjudicationOut(
        id=a.id,
        rubric_item_id=a.rubric_item_id,
        grade=a.grade_number,
        subject=a.subject_code,
        from_version_ids=a.from_version_ids,
        to_version_id=a.to_version_id,
        reason=a.reason,
        status=a.status,
        supersedes_ids=a.supersedes_ids or [],
        retained_descendant_ids=a.retained_descendant_ids or [],
        superseded_by_id=a.superseded_by_id,
        approved_at=a.approved_at,
        compatibility=a.compatibility,
        impact=adjudication.preview(db, a) if detail else None,
        latest_job=_job_out(job) if job else None,
    )


@router.get(
    "/studio/written/adjudication-sources",
    response_model=AdjudicationSourcesOut,
    summary="What a correction of this rubric could apply to: versions, compatibility and active corrections",
)
def adjudication_sources(
    db: DB, who: Reviewer, rubric_item_id: uuid.UUID, response: Response
) -> AdjudicationSourcesOut:
    from portal_api.modules.written import adjudication

    _private(response)
    return AdjudicationSourcesOut(**adjudication.sources(db, who, rubric_item_id))


@router.post(
    "/studio/written/adjudications",
    response_model=AdjudicationOut,
    status_code=201,
    summary="Apply a published rubric correction to earlier work (academic adjudicators in scope, MFA; audited)",
)
def create_adjudication(db: DB, who: Adjudicator, body: AdjudicationIn, response: Response) -> AdjudicationOut:
    from portal_api.modules.written import adjudication

    _private(response)
    a = adjudication.create(
        db,
        who,
        rubric_item_id=body.rubric_item_id,
        reason=body.reason,
        from_version_ids=body.from_version_ids,
        supersedes_ids=body.supersedes_ids,
        retain_descendant_ids=body.retain_descendant_ids,
    )
    return _adj_out(db, a, detail=True)


@router.get("/studio/written/adjudications", response_model=list[AdjudicationOut])
def list_adjudications(
    db: DB,
    who: Reviewer,
    response: Response,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[AdjudicationOut]:
    from portal_api.modules.written import adjudication

    _private(response)
    return [_adj_out(db, a, detail=False) for a in adjudication.visible(db, who, offset, limit)]


@router.get("/studio/written/adjudications/{adjudication_id}", response_model=AdjudicationOut)
def get_adjudication(db: DB, who: Reviewer, adjudication_id: uuid.UUID, response: Response) -> AdjudicationOut:
    from portal_api.modules.written import adjudication

    _private(response)
    return _adj_out(db, adjudication.get(db, who, adjudication_id), detail=True)


@router.get("/studio/written/adjudications/{adjudication_id}/attempts", response_model=RegradeAttemptsOut)
def adjudication_attempts(
    db: DB,
    who: Reviewer,
    adjudication_id: uuid.UUID,
    response: Response,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> RegradeAttemptsOut:
    from portal_api.modules.written import adjudication

    _private(response)
    return RegradeAttemptsOut(
        **adjudication.attempts_page(db, adjudication.get(db, who, adjudication_id), offset, limit)
    )


@router.post(
    "/studio/written/adjudications/{adjudication_id}/run",
    response_model=RegradeJobOut,
    status_code=202,
    summary="Queue the regrade for the worker (one open job per correction; repeating returns it)",
)
def run_adjudication(db: DB, who: Adjudicator, adjudication_id: uuid.UUID, response: Response) -> RegradeJobOut:
    from portal_api.modules.written import regrade_jobs

    _private(response)
    return _job_out(regrade_jobs.request_run(db, who, adjudication_id))


@router.get("/studio/written/regrade-jobs/{job_id}", response_model=RegradeJobOut)
def get_regrade_job(db: DB, who: Reviewer, job_id: uuid.UUID, response: Response) -> RegradeJobOut:
    from portal_api.modules.written import regrade_jobs

    _private(response)
    return _job_out(regrade_jobs.get(db, who, job_id))


@router.post("/studio/written/regrade-jobs/{job_id}/retry", response_model=RegradeJobOut)
def retry_regrade_job(db: DB, who: Adjudicator, job_id: uuid.UUID, response: Response) -> RegradeJobOut:
    from portal_api.modules.written import regrade_jobs

    _private(response)
    return _job_out(regrade_jobs.retry(db, who, job_id))


# ------------------------------------------------------------------ ACADEMIC-REVIEW-01 (W01.S2.T2, W05.S2.T3)
class AcademicReviewOut(BaseModel):
    id: uuid.UUID
    reference: str = Field(description="The script reference markers see (the learner is never named)")
    position: int
    grade: int
    subject: str
    kind: Literal["unlisted_method", "rubric_defect"]
    reason: str = Field(description="What the teacher wrote")
    rubric_item_id: uuid.UUID | None
    rubric_version: int | None
    raised_at: datetime
    status: Literal["open", "resolved"]
    resolution: Literal["guide_corrected", "not_covered"] | None
    resolution_note: str | None
    adjudication_id: uuid.UUID | None
    resolved_at: datetime | None


class AcademicResolveIn(BaseModel):
    resolution: Literal["guide_corrected", "not_covered"]
    note: str = Field(min_length=10, max_length=2000, description="Why, for the marker and the record")
    adjudication_id: uuid.UUID | None = Field(
        default=None, description="For guide_corrected: the approved correction of this question's marking guide"
    )


def _academic_out(db: Session, r: Any) -> AcademicReviewOut:
    rv = db.get(ContentVersion, r.rubric_version_id) if r.rubric_version_id else None
    return AcademicReviewOut(
        id=r.id,
        reference=str(r.attempt_id)[:8],
        position=r.position,
        grade=r.grade_number,
        subject=r.subject_code,
        kind=r.kind,
        reason=r.reason,
        rubric_item_id=rv.item_id if rv is not None else None,
        rubric_version=rv.number if rv is not None else None,
        raised_at=r.raised_at,
        status=r.status,
        resolution=r.resolution,
        resolution_note=r.resolution_note,
        adjudication_id=r.adjudication_id,
        resolved_at=r.resolved_at,
    )


@router.get(
    "/studio/written/academic-reviews",
    response_model=list[AcademicReviewOut],
    summary="Questions a teacher sent to academic review, in your academic scope (oldest first)",
)
def list_academic_reviews(
    db: DB,
    who: Reviewer,
    response: Response,
    status: Annotated[Literal["open", "resolved"], Query()] = "open",
) -> list[AcademicReviewOut]:
    from portal_api.modules.written import academic

    _private(response)
    return [_academic_out(db, r) for r in academic.visible(db, who, status)]


@router.post(
    "/studio/written/academic-reviews/{review_id}/resolve",
    response_model=AcademicReviewOut,
    summary="Decide how the marking guide applies (academic adjudicator with MFA); never sets a mark",
)
def resolve_academic_review(
    db: DB, who: Adjudicator, review_id: uuid.UUID, body: AcademicResolveIn, response: Response
) -> AcademicReviewOut:
    from portal_api.modules.written import academic

    _private(response)
    r = academic.resolve(db, who, review_id, body.resolution, body.note, body.adjudication_id)
    return _academic_out(db, r)


# ------------------------------------------------------------------ REVIEWER-QUALITY-01 (W06.S3.T3, part)
class ReviewerQualityOut(BaseModel):
    reviewer_id: uuid.UUID
    reviewer: str = Field(description="The marker's sign-in email (staff accountability; never a learner)")
    scopes: list[str] = Field(description="grade:subject pairs the marker decided in, within your scope")
    decisions: int = Field(description="Released teacher decisions in the window")
    rechecked: int = Field(description="Of the marker's decisions, how many a learner asked to recheck")
    changed_on_recheck: int = Field(description="Rechecks where another teacher changed the marks")
    upheld_on_recheck: int = Field(description="Rechecks where the marks stood")
    teacher_regrades: int = Field(description="Times an approved guide correction sent the marker's work to a teacher")
    academic_reviews_raised: int = Field(description="Methods the marker sent to academic review")


@router.get(
    "/studio/written/reviewer-quality",
    response_model=list[ReviewerQualityOut],
    summary="Per-marker overrides, upheld rechecks and conflicts in your academic scope (adjudicators)",
)
def reviewer_quality(
    db: DB, who: Adjudicator, response: Response, days: Annotated[int, Query(ge=7, le=365)] = 90
) -> list[ReviewerQualityOut]:
    from portal_api.modules.written import quality

    _private(response)
    return [ReviewerQualityOut(**r) for r in quality.report(db, who, days)]
