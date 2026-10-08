"""Separate new learning attempts (W04.S3.T3; §20.7.3, §20.13.4; WA-AC24).

New or improved work is never marked as if it were the sealed original. A learner who wants it marked starts a linked
new practice attempt: a new form holding the chosen questions of the original test, then the ordinary start path, so
it gets its own reservation and ledger identity and uses allowance like any other test. The original attempt, its
evidence and every released result stay exactly as they were; a recheck (same evidence, re-marked) stays a separate
route. Reasons:

- NEW_CONTENT: a learner rescan the reviewer classified as new or changed work.
- INDETERMINATE: a rescan whose sameness couldn't be established; explicit new practice is offered instead.
- REWRITE: the learner wants to answer again after seeing the released feedback.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from portal_api.errors import Conflict, NotFound, Unprocessable
from portal_api.modules.access import service as access
from portal_api.modules.audit.models import record
from portal_api.modules.content import written as wq
from portal_api.modules.content.models import Availability, ContentItem, ContentVersion
from portal_api.modules.identity.deps import Principal
from portal_api.modules.written import review, service
from portal_api.modules.written.models import WrittenAttempt, WrittenForm, WrittenFormItem

REASONS = ("NEW_CONTENT", "INDETERMINATE", "REWRITE")


def create_linked_form(
    db: Session,
    who: Principal,
    origin_attempt_id: uuid.UUID,
    *,
    reason: str,
    positions: list[int],
    revision_id: uuid.UUID | None,
    idempotency_key: str,
) -> WrittenForm:
    chosen = sorted(set(positions))
    req = {
        "origin": str(origin_attempt_id),
        "reason": reason,
        "positions": chosen,
        "revision": str(revision_id) if revision_id else None,
    }
    rhash = hashlib.sha256(json.dumps(req, sort_keys=True).encode()).hexdigest()
    existing = db.scalar(
        select(WrittenForm).where(WrittenForm.owner_id == who.user.id, WrittenForm.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.request_hash != rhash:
            raise Conflict("This request key was already used for a different test.", code_reason="KEY_REUSED")
        return existing
    origin = db.get(WrittenAttempt, origin_attempt_id)
    if origin is None or origin.user_id != who.user.id:
        raise NotFound("Attempt not found.")
    if origin.status != "sealed":
        raise Unprocessable("Only a submitted test can be practised again.", code_reason="NOT_SEALED")
    origin_form = db.get(WrittenForm, origin.form_id)
    assert origin_form is not None
    by_pos = {fi.position: fi for fi in origin_form.items}
    if not chosen or not set(chosen) <= set(by_pos):
        raise Unprocessable("Choose questions from the original test.", code_reason="LINK_NOT_ELIGIBLE")
    if reason == "REWRITE":
        if revision_id is not None:
            raise Unprocessable("A rewrite isn't tied to a rescan.", code_reason="LINK_NOT_ELIGIBLE")
        if review.released_result(db, origin.id) is None:
            raise Unprocessable(
                "You can practise these questions again once your result is released. If a teacher misread your "
                "answer, ask for a recheck instead.",
                code_reason="RESULT_NOT_RELEASED",
            )
    else:
        from portal_api.modules.written.rescans import EvidenceRevision

        rev = db.get(EvidenceRevision, revision_id) if revision_id is not None else None
        if rev is None or rev.attempt_id != origin.id or rev.classification != reason or rev.position not in chosen:
            raise Unprocessable(
                "That copy wasn't classified as new or unclear work for these questions.",
                code_reason="LINK_NOT_ELIGIBLE",
            )
    access.require_access(db, who.user.id, purpose="Written practice")
    if not service.review_staffed(db, origin_form.grade_number, origin_form.subject_code):
        raise Unprocessable(
            "Written practice for this subject isn't offered yet: no teacher reviewer is available to mark it."
        )
    # The questions as they are published now: a question withdrawn or corrected since is never offered stale.
    items = {
        i.id: i for i in db.scalars(select(ContentItem).where(ContentItem.id.in_([by_pos[p].item_id for p in chosen])))
    }
    rubrics = service._live_rubric_versions(db, [i for i in items.values() if i.published_version_id is not None])
    # PR32-03: read everything first, then add the new rows and flush them inside the one guarded unit of work, so no
    # read can autoflush a conflicting insert outside the idempotency handling.
    form_id = uuid.uuid4()
    rows: list[WrittenFormItem] = []
    total = 0
    changed: list[int] = []
    for new_pos, old_pos in enumerate(chosen, start=1):
        fi = by_pos[old_pos]
        item = items.get(fi.item_id)
        if item is None or item.availability != Availability.live.value or item.id not in rubrics:
            db.rollback()
            raise Unprocessable(
                f"Question {old_pos} is no longer offered for practice, so it can't be practised again.",
                code_reason="QUESTION_WITHDRAWN",
            )
        assert item.published_version_id is not None
        qv = db.get(ContentVersion, item.published_version_id)
        assert qv is not None
        q, _ = wq.parse_written(qv.body)
        assert q is not None
        if qv.id != fi.question_version_id:
            changed.append(old_pos)  # the new attempt uses the corrected version; the original keeps its pinned one
        total += q.max_units
        rows.append(
            WrittenFormItem(
                form_id=form_id,
                position=new_pos,
                item_id=item.id,
                family_id=fi.family_id,
                question_version_id=qv.id,
                rubric_version_id=rubrics[item.id].id,
                max_units=q.max_units,
                slots=[service.slot_key(new_pos, s) for s in wq.subpart_maxima(q)],
            )
        )
    form = WrittenForm(
        id=form_id,
        owner_id=who.user.id,
        idempotency_key=idempotency_key,
        request_hash=rhash,
        grade_number=origin_form.grade_number,
        subject_code=origin_form.subject_code,
        scope=origin_form.scope,
        seed=origin_form.seed,
        question_type=origin_form.question_type,
        writing_s=origin_form.writing_s,
        upload_allowance_s=origin_form.upload_allowance_s,
        caps=service.CAPS,
        max_units=total,
        linked_from_attempt_id=origin.id,
        link_reason=reason,
        link_revision_id=revision_id,
        link_positions=chosen,
    )
    try:
        db.add(form)
        db.flush()  # the form first: only it carries the owner/key constraint
        db.add_all(rows)
        record(
            db,
            actor=who.user.id,
            action="written.linked_form",
            target_type="written_form",
            target_id=str(form.id),
            details={**req, "updated_questions": changed},
        )
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if getattr(getattr(e.orig, "diag", None), "constraint_name", None) != "uq_written_form_idempotency":
            raise  # any other integrity failure is a real error, never a replay
        winner = db.scalar(
            select(WrittenForm).where(
                WrittenForm.owner_id == who.user.id, WrittenForm.idempotency_key == idempotency_key
            )
        )
        if winner is None or winner.request_hash != rhash:
            raise Conflict(
                "This request key was already used for a different test.", code_reason="KEY_REUSED"
            ) from None
        return winner
    db.refresh(form)
    return form


def allowance_units(db: Session, form: WrittenForm) -> int:
    """The weighted allowance units starting this form reserves (§20.13.4), shown before the learner starts it."""
    return service._form_units(db, form)


def linked_attempts(db: Session, origin_attempt_id: uuid.UUID) -> list[dict[str, Any]]:
    """Every new practice test linked to this attempt, oldest first, with its own attempt if it was started."""
    out = []
    forms = db.scalars(
        select(WrittenForm)
        .where(WrittenForm.linked_from_attempt_id == origin_attempt_id)
        .order_by(WrittenForm.created_at, WrittenForm.id)
    )
    for f in forms:
        attempt = db.scalar(select(WrittenAttempt).where(WrittenAttempt.form_id == f.id))
        out.append(
            {
                "form_id": f.id,
                "attempt_id": attempt.id if attempt else None,
                "status": attempt.status if attempt else "not_started",
                "reason": f.link_reason,
                "positions": f.link_positions or [],
                "created_at": f.created_at,
            }
        )
    return out
