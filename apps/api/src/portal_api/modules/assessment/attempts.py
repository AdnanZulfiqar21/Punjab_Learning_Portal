"""Attempt runtime implementing the §10.5 submission and deadline contract (P10.S1 to P10.S3).

Every write path follows the same order: authenticate → bounded validation → lock the attempt row → read the database
clock *after* the lock (`admitted_at`) → decide each operation against D/T/C and the committed ledger → commit → reply.
Nothing slow or remote happens under the lock. Only committed operations are acknowledged as saved.

Operation dispositions:
  accepted   newer valid revision admitted at or before the cutoff C
  stale      an older (or equal) revision than the committed one; never overwrites newer work
  invalid    unknown position or option
  late       admitted after C (the client may have selected it earlier; arrival is not admission)
  finalised  the attempt was already finalised when this new operation arrived
  locked     the item's feedback was revealed (immediate-feedback practice), so it can't change
  conflict   an op_id reused with a different payload (not stored; the original stands)
An exact replay of a stored op_id returns its original disposition, including after finalisation.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from portal_api.errors import AttemptFinalised, Conflict, NotFound, Unprocessable
from portal_api.modules.assessment import forms, scoring
from portal_api.modules.assessment.models import (
    SCORING_POLICY_VERSION,
    AnswerOp,
    Attempt,
    AttemptAnswer,
    FormItem,
    PracticeForm,
    ScoreVersion,
    SubmissionReceipt,
)
from portal_api.modules.audit.models import record
from portal_api.modules.identity.deps import Principal

MAX_OPS = 50


@dataclass(frozen=True)
class Op:
    op_id: uuid.UUID
    position: int
    revision: int
    option_id: str | None

    @property
    def payload_hash(self) -> str:
        return hashlib.sha256(json.dumps([self.position, self.revision, self.option_id]).encode()).hexdigest()


def db_now(db: Session) -> datetime:
    """Trusted database wall clock at this moment (not the transaction start), read after taking the lock."""
    now: datetime = db.execute(select(func.clock_timestamp())).scalar_one()
    return now


# ------------------------------------------------------------------ start
def start(db: Session, who: Principal, form_id: uuid.UUID) -> Attempt:
    form = db.get(PracticeForm, form_id)
    if form is None or form.owner_id != who.user.id:
        raise NotFound("Test not found.")
    existing = db.scalar(select(Attempt).where(Attempt.form_id == form_id, Attempt.user_id == who.user.id))
    if existing is not None:
        return existing  # starting is idempotent: one attempt per personal practice form
    if forms.superseded_positions(db, form):
        # §5.7 before start: a question was quarantined, corrected or replaced since this test was built. The shared
        # original is never mutated; the learner builds a new test from the approved versions.
        raise Conflict(
            "A question in this test was corrected or is under review since it was built. Build a new test.",
            code_reason="FORM_SUPERSEDED",
        )
    now = db_now(db)
    deadline = now + timedelta(seconds=form.duration_s) if form.duration_s else None
    cutoff = deadline + timedelta(milliseconds=form.late_write_tolerance_ms) if deadline else None
    db.execute(
        insert(Attempt)
        .values(
            id=uuid.uuid4(),
            form_id=form.id,
            user_id=who.user.id,
            status="active",
            started_at=now,
            deadline_at=deadline,
            tolerance_ms=form.late_write_tolerance_ms,
            cutoff_at=cutoff,
        )
        .on_conflict_do_nothing(constraint="uq_attempt_form_user")
    )
    db.commit()
    attempt = db.scalar(select(Attempt).where(Attempt.form_id == form_id, Attempt.user_id == who.user.id))
    assert attempt is not None
    return attempt


# ------------------------------------------------------------------ helpers
def _lock(db: Session, attempt_id: uuid.UUID, who: Principal) -> Attempt:
    attempt = db.scalar(select(Attempt).where(Attempt.id == attempt_id).with_for_update())
    if attempt is None or attempt.user_id != who.user.id:
        raise NotFound("Attempt not found.")
    return attempt


def _items(db: Session, attempt: Attempt) -> dict[int, FormItem]:
    return {fi.position: fi for fi in db.scalars(select(FormItem).where(FormItem.form_id == attempt.form_id))}


def _receipt_of(op: AnswerOp, *, replay: bool) -> dict[str, Any]:
    return {
        "op_id": op.op_id,
        "position": op.position,
        "revision": op.revision,
        "option_id": op.option_id,
        "disposition": op.disposition,
        "admitted_at": op.admitted_at,
        "replay": replay,
    }


def _apply(
    db: Session, attempt: Attempt, items: dict[int, FormItem], op: Op, now: datetime, via: str
) -> dict[str, Any]:
    stored = db.scalar(select(AnswerOp).where(AnswerOp.attempt_id == attempt.id, AnswerOp.op_id == op.op_id))
    if stored is not None:
        if stored.payload_hash == op.payload_hash:
            return _receipt_of(stored, replay=True)
        return {
            "op_id": op.op_id,
            "position": op.position,
            "revision": op.revision,
            "option_id": op.option_id,
            "disposition": "conflict",
            "admitted_at": now,
            "replay": False,
        }
    if attempt.status != "active":
        disposition = "finalised"
    elif attempt.cutoff_at is not None and now > attempt.cutoff_at:
        disposition = "late"
    elif op.position not in items or (op.option_id is not None and op.option_id not in items[op.position].option_order):
        disposition = "invalid"
    else:
        current = db.get(AttemptAnswer, (attempt.id, op.position))
        if current is not None and current.revealed_at is not None:
            disposition = "locked"
        elif current is not None and op.revision <= current.revision:
            disposition = "stale"
        else:
            disposition = "accepted"
            if current is None:
                db.add(
                    AttemptAnswer(
                        attempt_id=attempt.id,
                        position=op.position,
                        option_id=op.option_id,
                        revision=op.revision,
                        op_id=op.op_id,
                        saved_at=now,
                    )
                )
            else:
                current.option_id = op.option_id
                current.revision = op.revision
                current.op_id = op.op_id
                current.saved_at = now
    row = AnswerOp(
        attempt_id=attempt.id,
        op_id=op.op_id,
        payload_hash=op.payload_hash,
        position=op.position,
        revision=op.revision,
        option_id=op.option_id,
        admitted_at=now,
        disposition=disposition,
        via=via,
    )
    db.add(row)
    db.flush()
    return _receipt_of(row, replay=False)


def _answers(db: Session, attempt: Attempt) -> dict[int, str | None]:
    rows = db.scalars(select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt.id))
    return {a.position: a.option_id for a in rows}


def _finalise(
    db: Session,
    attempt: Attempt,
    now: datetime,
    *,
    reason: str,
    idempotency_key: str | None,
    results: list[dict[str, Any]],
    actor: uuid.UUID | None,
) -> SubmissionReceipt:
    answers = _answers(db, attempt)
    form = db.get(PracticeForm, attempt.form_id)
    assert form is not None
    attempt.status = "finalised"
    attempt.finalised_at = now
    attempt.finalise_reason = reason
    receipt = SubmissionReceipt(
        attempt_id=attempt.id,
        idempotency_key=idempotency_key,
        reason=reason,
        admitted_at=now,
        answered_count=sum(1 for v in answers.values() if v is not None),
        question_count=form.question_count,
        ledger_hash=scoring.ledger_hash(answers),
        included_ops=[{"op_id": str(r["op_id"]), "disposition": r["disposition"]} for r in results],
    )
    db.add(receipt)
    _score(db, attempt, form, answers, reason=f"finalised ({reason})")
    record(
        db,
        actor=actor,
        action=f"attempt.finalised.{reason}",
        target_type="attempt",
        target_id=str(attempt.id),
        details={"answered": receipt.answered_count, "ledger_hash": receipt.ledger_hash},
    )
    db.flush()
    return receipt


def _score(
    db: Session, attempt: Attempt, form: PracticeForm, answers: dict[int, str | None], *, reason: str
) -> ScoreVersion:
    from portal_api.modules.assessment.adjudications import effective_for_form

    keys = forms.item_keys(db, form)
    adjs = effective_for_form(db, form)  # corrections recorded while the attempt was open apply at submission
    result = scoring.score(
        [
            scoring.ItemKey(
                position=p, correct_option_id=k["correct_option_id"], option_ids=k["option_ids"], marks=k["marks"]
            )
            for p, k in keys.items()
        ],
        answers,
        negative_marks=form.negative_marks,
        adjudications=adjs,
    )
    sv = ScoreVersion(
        attempt_id=attempt.id,
        version=1,
        scoring_policy_version=SCORING_POLICY_VERSION,
        adjudication_hash=scoring.adjudication_hash(adjs),
        status=result.status,
        raw=result.raw,
        maximum=result.maximum,
        percentage=result.percentage,
        items=result.items,
        reason=reason,
    )
    db.add(sv)
    return sv


def _expire_if_due(db: Session, attempt: Attempt, now: datetime) -> SubmissionReceipt | None:
    """Automatic expiry under the attempt lock, only when the locked clock is strictly after C (§10.5)."""
    if attempt.status == "active" and attempt.cutoff_at is not None and now > attempt.cutoff_at:
        return _finalise(db, attempt, now, reason="expiry", idempotency_key=None, results=[], actor=None)
    return None


def receipt_for(db: Session, attempt_id: uuid.UUID) -> SubmissionReceipt | None:
    return db.scalar(select(SubmissionReceipt).where(SubmissionReceipt.attempt_id == attempt_id))


# ------------------------------------------------------------------ reads
def load(db: Session, who: Principal, attempt_id: uuid.UUID) -> Attempt:
    """Resume an attempt. Expires it first (under the lock) if its cutoff has passed."""
    attempt = _lock(db, attempt_id, who)
    _expire_if_due(db, attempt, db_now(db))
    db.commit()
    db.refresh(attempt)
    return attempt


def answers_view(db: Session, attempt: Attempt) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt.id).order_by(AttemptAnswer.position)
    )
    return [
        {
            "position": a.position,
            "option_id": a.option_id,
            "revision": a.revision,
            "op_id": a.op_id,
            "saved_at": a.saved_at,
            "revealed": a.revealed_at is not None,
        }
        for a in rows
    ]


# ------------------------------------------------------------------ writes
def save(db: Session, who: Principal, attempt_id: uuid.UUID, ops: list[Op]) -> dict[str, Any]:
    if len(ops) > MAX_OPS:
        raise Unprocessable(f"Send at most {MAX_OPS} operations at a time.")
    attempt = _lock(db, attempt_id, who)
    was_final = attempt.status != "active"
    now = db_now(db)
    items = _items(db, attempt)
    results = [_apply(db, attempt, items, op, now, "save") for op in ops]
    _expire_if_due(db, attempt, now)  # after recording the late ops, so they keep their 'late' reason
    db.commit()
    receipt = receipt_for(db, attempt.id)
    out = {"status": attempt.status, "results": results, "receipt_id": receipt.id if receipt else None}
    if was_final and any(r["disposition"] == "finalised" for r in results):
        extras = _jsonable(
            {"attempt_status": out["status"], "results": out["results"], "receipt_id": out["receipt_id"]}
        )
        raise AttemptFinalised("This attempt has already been submitted.", **extras)
    return out


def submit(db: Session, who: Principal, attempt_id: uuid.UUID, idempotency_key: str, ops: list[Op]) -> dict[str, Any]:
    """Explicit manual submission: apply the final pending operations and finalise once, under one lock (§10.5)."""
    if len(ops) > MAX_OPS:
        raise Unprocessable(f"Send at most {MAX_OPS} operations at a time.")
    attempt = _lock(db, attempt_id, who)
    now = db_now(db)
    items = _items(db, attempt)
    existing = receipt_for(db, attempt.id)
    if existing is not None:
        # Already finalised (by this request, another submit, or expiry): return the same logical receipt, plus a
        # separate reconciliation report for any operations presented now. The receipt is never rewritten.
        results = [_apply(db, attempt, items, op, now, "submit") for op in ops]
        db.commit()
        return {
            "receipt": existing,
            "same_request": existing.idempotency_key == idempotency_key,
            "reconciliation": results,
        }
    results = [_apply(db, attempt, items, op, now, "submit") for op in ops]
    if attempt.status == "active":
        # A manual submit admitted after C can't add answers (its ops are 'late'); it finalises the committed ledger.
        reason = "expiry" if attempt.cutoff_at is not None and now > attempt.cutoff_at else "manual"
        receipt = _finalise(
            db, attempt, now, reason=reason, idempotency_key=idempotency_key, results=results, actor=who.user.id
        )
    else:  # pragma: no cover - a receipt always exists for finalised attempts
        raise Conflict("This attempt is not active.")
    db.commit()
    return {"receipt": receipt, "same_request": True, "reconciliation": []}


def reveal(db: Session, who: Principal, attempt_id: uuid.UUID, position: int) -> dict[str, Any]:
    """Immediate-feedback practice: show one item's key and explanation; its answer is then locked."""
    attempt = _lock(db, attempt_id, who)
    form = db.get(PracticeForm, attempt.form_id)
    assert form is not None
    if form.feedback_mode != "immediate" and attempt.status == "active":
        raise Conflict("Feedback for this test is shown after you submit.")
    answer = db.get(AttemptAnswer, (attempt.id, position))
    if attempt.status == "active":
        if answer is None or answer.option_id is None:
            raise Unprocessable("Choose and save an answer before checking it.")
        if answer.revealed_at is None:
            answer.revealed_at = db_now(db)
    keys = forms.item_keys(db, form)
    if position not in keys:
        raise NotFound("Question not found in this test.")
    db.commit()
    k = keys[position]
    return {
        "position": position,
        "chosen": answer.option_id if answer else None,
        "correct_option_id": k["correct_option_id"],
        "correct": bool(answer and answer.option_id == k["correct_option_id"]),
        "explanation": k["explanation"],
    }


def expire_due(db: Session, limit: int = 200) -> int:
    """Worker entry point: finalise attempts whose cutoff has passed. Skips rows another transaction holds."""
    done = 0
    ids = db.scalars(
        select(Attempt.id)
        .where(Attempt.status == "active", Attempt.cutoff_at.is_not(None), Attempt.cutoff_at < func.now())
        .order_by(Attempt.cutoff_at)
        .limit(limit)
    ).all()
    for attempt_id in ids:
        attempt = db.scalar(select(Attempt).where(Attempt.id == attempt_id).with_for_update(skip_locked=True))
        if attempt is None:
            db.rollback()
            continue
        if _expire_if_due(db, attempt, db_now(db)) is not None:
            done += 1
        db.commit()
    return done


def latest_score(db: Session, attempt_id: uuid.UUID) -> ScoreVersion | None:
    return db.scalar(
        select(ScoreVersion).where(ScoreVersion.attempt_id == attempt_id).order_by(ScoreVersion.version.desc()).limit(1)
    )


def _jsonable(out: dict[str, Any]) -> dict[str, Any]:
    converted: dict[str, Any] = json.loads(json.dumps(out, default=str))
    return converted
