"""Learner practice and attempt API (P09/P10). All responses are private (`no-store`)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.orm import Session

from portal_api.db import get_session
from portal_api.errors import Conflict, NotFound
from portal_api.modules.assessment import attempts, forms
from portal_api.modules.assessment.models import Attempt, PracticeForm, SubmissionReceipt
from portal_api.modules.assessment.schemas import (
    AnswerOut,
    AttemptOut,
    AvailabilityOut,
    ChapterAvailability,
    FormCreateIn,
    FormOut,
    ItemReview,
    ItemSnapshot,
    OpIn,
    OpResult,
    OpsIn,
    ReceiptOut,
    ResultOut,
    RevealOut,
    SaveOut,
    SubmitIn,
    SubmitOut,
)
from portal_api.modules.identity.deps import CurrentPrincipal

router = APIRouter(prefix="/v1", tags=["practice"])
DB = Annotated[Session, Depends(get_session)]


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _ops(items: list[OpIn]) -> list[attempts.Op]:
    return [attempts.Op(op_id=o.op_id, position=o.position, revision=o.revision, option_id=o.option_id) for o in items]


def _form_out(f: PracticeForm) -> FormOut:
    return FormOut(
        id=f.id,
        grade=f.grade_number,
        subject=f.subject_code,
        scope=f.scope,
        question_count=f.question_count,
        duration_s=f.duration_s,
        late_write_tolerance_ms=f.late_write_tolerance_ms,
        feedback_mode=f.feedback_mode,  # type: ignore[arg-type]
        negative_marks=f.negative_marks,
        created_at=f.created_at,
    )


def _receipt_out(r: SubmissionReceipt) -> ReceiptOut:
    return ReceiptOut(
        id=r.id,
        reason=r.reason,  # type: ignore[arg-type]
        admitted_at=r.admitted_at,
        answered_count=r.answered_count,
        question_count=r.question_count,
        ledger_hash=r.ledger_hash,
    )


def _attempt_out(db: Session, a: Attempt) -> AttemptOut:
    form = db.get(PracticeForm, a.form_id)
    assert form is not None
    receipt = attempts.receipt_for(db, a.id)
    return AttemptOut(
        id=a.id,
        form_id=a.form_id,
        status=a.status,  # type: ignore[arg-type]
        started_at=a.started_at,
        deadline_at=a.deadline_at,
        cutoff_at=a.cutoff_at,
        tolerance_ms=a.tolerance_ms,
        server_now=attempts.db_now(db),
        feedback_mode=form.feedback_mode,  # type: ignore[arg-type]
        items=[ItemSnapshot(**i) for i in forms.learner_items(db, form)],
        answers=[AnswerOut(**x) for x in attempts.answers_view(db, a)],
        receipt=_receipt_out(receipt) if receipt else None,
    )


@router.get("/practice/availability", response_model=AvailabilityOut, summary="Approved questions per chapter")
def availability(
    db: DB,
    _: CurrentPrincipal,
    response: Response,
    grade: Annotated[int, Query(ge=11, le=12)],
    subject: Annotated[str, Query(min_length=2, max_length=40)],
) -> AvailabilityOut:
    _private(response)
    rows = forms.availability(db, grade, subject)
    return AvailabilityOut(grade=grade, subject=subject, chapters=[ChapterAvailability(**r) for r in rows])


@router.post("/practice/forms", response_model=FormOut, status_code=201, summary="Generate and freeze a practice test")
def create_form(
    db: DB,
    who: CurrentPrincipal,
    body: FormCreateIn,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=80)],
) -> FormOut:
    _private(response)
    form = forms.create_form(
        db,
        who,
        idempotency_key=idempotency_key,
        grade=body.grade,
        subject=body.subject,
        chapter_ids=body.chapter_ids,
        topic_ids=body.topic_ids,
        question_count=body.question_count,
        timed_minutes=body.timed_minutes,
        feedback_mode=body.feedback_mode,
    )
    return _form_out(form)


@router.post("/practice/forms/{form_id}/attempt", response_model=AttemptOut, summary="Start (or resume) the attempt")
def start_attempt(db: DB, who: CurrentPrincipal, form_id: uuid.UUID, response: Response) -> AttemptOut:
    _private(response)
    attempt = attempts.start(db, who, form_id)
    return _attempt_out(db, attempts.load(db, who, attempt.id))


@router.get("/attempts/{attempt_id}", response_model=AttemptOut, summary="Resume: questions, saved answers, timing")
def get_attempt(db: DB, who: CurrentPrincipal, attempt_id: uuid.UUID, response: Response) -> AttemptOut:
    _private(response)
    return _attempt_out(db, attempts.load(db, who, attempt_id))


@router.post("/attempts/{attempt_id}/answers", response_model=SaveOut, summary="Save answer operations (§10.5)")
def save_answers(db: DB, who: CurrentPrincipal, attempt_id: uuid.UUID, body: OpsIn, response: Response) -> SaveOut:
    _private(response)
    out = attempts.save(db, who, attempt_id, _ops(body.ops))
    return SaveOut(status=out["status"], results=[OpResult(**r) for r in out["results"]], receipt_id=out["receipt_id"])


@router.post("/attempts/{attempt_id}/submit", response_model=SubmitOut, summary="Final submission (idempotent)")
def submit(db: DB, who: CurrentPrincipal, attempt_id: uuid.UUID, body: SubmitIn, response: Response) -> SubmitOut:
    _private(response)
    out = attempts.submit(db, who, attempt_id, body.idempotency_key, _ops(body.ops))
    return SubmitOut(
        receipt=_receipt_out(out["receipt"]),
        same_request=out["same_request"],
        reconciliation=[OpResult(**r) for r in out["reconciliation"]],
    )


@router.post(
    "/attempts/{attempt_id}/items/{position}/reveal",
    response_model=RevealOut,
    summary="Immediate-feedback practice: check one saved answer (locks it)",
)
def reveal(db: DB, who: CurrentPrincipal, attempt_id: uuid.UUID, position: int, response: Response) -> RevealOut:
    _private(response)
    return RevealOut(**attempts.reveal(db, who, attempt_id, position))


@router.get("/attempts/{attempt_id}/result", response_model=ResultOut, summary="Score and review after submission")
def result(db: DB, who: CurrentPrincipal, attempt_id: uuid.UUID, response: Response) -> ResultOut:
    _private(response)
    attempt = attempts.load(db, who, attempt_id)
    if attempt.status != "finalised":
        raise Conflict("Results are available after you submit.")
    score = attempts.latest_score(db, attempt.id)
    receipt = attempts.receipt_for(db, attempt.id)
    form = db.get(PracticeForm, attempt.form_id)
    if score is None or receipt is None or form is None:
        raise NotFound("The result is not available yet.")
    keys = forms.item_keys(db, form)
    rows = {r["position"]: r for r in score.items}
    items = []
    for fi in form.items:
        k = keys[fi.position]
        r = rows[fi.position]
        items.append(
            ItemReview(
                position=fi.position,
                marks=fi.marks,
                stem=k["stem"],
                options=[{"id": oid, "blocks": k["options"][oid]["blocks"]} for oid in fi.option_order],  # type: ignore[misc]
                chosen=r["chosen"],
                correct_option_id=k["correct_option_id"],
                correct=r["correct"],
                earned=r["earned"],
                treatment=r["treatment"],
                explanation=k["explanation"],
            )
        )
    return ResultOut(
        attempt_id=attempt.id,
        version=score.version,
        status=score.status,  # type: ignore[arg-type]
        raw=score.raw,
        maximum=score.maximum,
        percentage=score.percentage,  # type: ignore[arg-type]
        answered=receipt.answered_count,
        question_count=receipt.question_count,
        finalise_reason=attempt.finalise_reason,  # type: ignore[arg-type]
        items=items,
    )
