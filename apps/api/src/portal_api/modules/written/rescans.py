"""Learner actions on pending questions: readability rescans and confirmed-unanswered (W04.S3.T2, W06.S2.T4, §20.7.3,
§20.6.3, §20.10 finite remedy; WA-AC62/63/82).

A teacher may leave a question pending and ask the learner to act within 7 days:

* ``rescan``: the work couldn't be read. The learner may upload a clearer copy of the **same** answer.
* ``confirm_or_rescan``: the mapped evidence looks blank. The learner may confirm they didn't answer, or rescan.

A rescan never replaces the sealed original. It is a linked, immutable :class:`EvidenceRevision` (hashes, the prior
pages it relates to, actor, note, time, always post-cutoff). The next completion reviewer compares original and
revision side by side and records READABILITY, NEW_CONTENT or INDETERMINATE with a reason; nothing classifies a
revision automatically. Only a READABILITY revision may be used to assess the original answer. NEW_CONTENT leaves the
original result as it is and the learner is offered a separate new practice attempt; INDETERMINATE keeps the question
pending until its deadline or unavailable.

A learner-confirmed unanswered question is resolved under the rubric (zero, maximum kept) and its unconsumed allowance
is released, the same treatment as declaring it unanswered before sealing. A question still awaiting the learner after
its deadline is resolved unavailable by the deadline job, with its allowance returned: silence is never consent and
never a zero.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, String, Text, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base
from portal_api.errors import Conflict, NotFound, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.content import written as wq
from portal_api.modules.content.models import ContentVersion
from portal_api.modules.identity.deps import Principal
from portal_api.modules.written import evidence, storage
from portal_api.modules.written.models import WrittenAttempt, WrittenFile, WrittenForm, WrittenPage, WrittenReceipt

MAX_REVISIONS_PER_QUESTION = 3  # processing abuse budget (WF-09)
MAX_REVISION_PAGES = 3
CLASSES = ("READABILITY", "NEW_CONTENT", "INDETERMINATE")


class EvidenceRevision(Base):
    __tablename__ = "written_evidence_revision"
    __table_args__ = (
        CheckConstraint(
            "classification is null or classification in ('READABILITY','NEW_CONTENT','INDETERMINATE')",
            name="written_revision_class",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_attempt.id", ondelete="RESTRICT"), index=True)
    position: Mapped[int] = mapped_column(SmallInteger)
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_file.id", ondelete="RESTRICT"))
    prior_page_ids: Mapped[list[str]] = mapped_column(JSONB)  # the sealed pages this revision relates to
    prior_hashes: Mapped[dict[str, str]] = mapped_column(JSONB)  # page id -> sealed original file hash
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    note: Mapped[str] = mapped_column(Text, default="")
    post_cutoff: Mapped[bool] = mapped_column(default=True)  # always after the upload cutoff U: the receipt is sealed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    classification: Mapped[str | None] = mapped_column(String(14))
    class_reason: Mapped[str | None] = mapped_column(Text)
    classified_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    classified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("written_review_case.id", ondelete="RESTRICT"))


def _now(db: Session) -> datetime:
    now: datetime = db.execute(select(func.clock_timestamp())).scalar_one()
    return now


def _lock_attempt(db: Session, attempt_id: uuid.UUID, who: Principal) -> WrittenAttempt:
    attempt = db.scalar(
        select(WrittenAttempt)
        .where(WrittenAttempt.id == attempt_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if attempt is None or attempt.user_id != who.user.id:
        raise NotFound("Attempt not found.")
    return attempt


def _requested_action(db: Session, attempt_id: uuid.UUID, position: int, now: datetime) -> dict[str, Any]:
    """The current released status of a question, which must be pending with a learner action still in time."""
    from portal_api.modules.written import review

    current = review.released_result(db, attempt_id)
    st = (current.question_status or {}).get(str(position), {}) if current else {}
    if st.get("status") != "pending" or st.get("learner_action") not in ("rescan", "confirm_or_rescan"):
        raise Conflict("No action is needed for this question.", code_reason="NO_LEARNER_ACTION")
    if now > datetime.fromisoformat(st["action_deadline"]):
        raise Conflict("The 7 days to act on this question have passed.", code_reason="ACTION_DEADLINE_PASSED")
    return dict(st)


def revisions_for(db: Session, attempt_id: uuid.UUID, positions: set[int] | None = None) -> list[EvidenceRevision]:
    stmt = select(EvidenceRevision).where(EvidenceRevision.attempt_id == attempt_id)
    if positions is not None:
        stmt = stmt.where(EvidenceRevision.position.in_(positions))
    return list(db.scalars(stmt.order_by(EvidenceRevision.created_at)))


def submit_rescan(
    db: Session, who: Principal, attempt_id: uuid.UUID, position: int, data: bytes, note: str
) -> EvidenceRevision:
    """Store a clearer copy of one pending answer as a linked revision. No connection is held while parsing or storing
    (DBHOLD-01); the request is re-checked under the attempt lock before anything is committed."""
    attempt = db.get(WrittenAttempt, attempt_id)
    if attempt is None or attempt.user_id != who.user.id:
        raise NotFound("Attempt not found.")
    if attempt.status != "sealed":
        raise Conflict("Rescans are for submitted scripts.")
    _requested_action(db, attempt_id, position, _now(db))
    if len(revisions_for(db, attempt_id, {position})) >= MAX_REVISIONS_PER_QUESTION:
        raise Conflict(
            f"You can send at most {MAX_REVISIONS_PER_QUESTION} clearer copies of one answer.",
            code_reason="RESCAN_LIMIT",
        )
    sha = hashlib.sha256(data).hexdigest()
    if db.scalar(select(WrittenFile.id).where(WrittenFile.attempt_id == attempt_id, WrittenFile.sha256 == sha)):
        raise Conflict(
            "This is the same file that was already sent. Take a new, clearer photo of the answer.",
            code_reason="SAME_FILE",
        )
    prefix = str(attempt.id)
    db.rollback()
    try:
        inspected = evidence.inspect(data)
    except evidence.Rejected as e:
        raise Unprocessable(e.reason, code_reason="UNSUPPORTED_FILE") from e
    if len(inspected.pages) > MAX_REVISION_PAGES:
        raise Unprocessable(f"A clearer copy can have at most {MAX_REVISION_PAGES} pages.", code_reason="PAGE_LIMIT")
    store = storage.get_store()
    file_id = uuid.uuid4()
    keys: list[str] = []
    try:
        original = store.put(f"{prefix}/revisions/{file_id}/original", data)
        keys.append(original.key)
        previews = []
        for i, lp in enumerate(inspected.pages, start=1):
            pv = store.put(f"{prefix}/revisions/{file_id}/page-{i}.png", lp.preview_png)
            keys.append(pv.key)
            previews.append((lp, pv))
        attempt = _lock_attempt(db, attempt_id, who)
        now = _now(db)
        _requested_action(db, attempt_id, position, now)
        if len(revisions_for(db, attempt_id, {position})) >= MAX_REVISIONS_PER_QUESTION:
            raise Conflict("Too many clearer copies for this answer.", code_reason="RESCAN_LIMIT")
        receipt = db.scalar(select(WrittenReceipt).where(WrittenReceipt.attempt_id == attempt_id))
        assert receipt is not None
        slots = receipt.manifest.get("slots", {})
        prior = sorted({p for k, v in slots.items() if k.split(":")[0] == str(position) for p in v.get("pages", [])})
        db.add(
            WrittenFile(
                id=file_id,
                attempt_id=attempt_id,
                storage_key=original.key,
                sha256=sha,
                size=original.size,
                content_type=inspected.content_type,
                page_count=len(previews),
                uploaded_at=now,
                status="revision",
            )
        )
        db.flush()
        for i, (lp, pv) in enumerate(previews, start=1):
            db.add(
                WrittenPage(
                    id=file_id if i == 1 else uuid.uuid4(),
                    attempt_id=attempt_id,
                    file_id=file_id,
                    page_index=i,
                    width=lp.width,
                    height=lp.height,
                    preview_key=pv.key,
                    preview_sha256=pv.sha256,
                    uploaded_at=now,
                    status="revision",
                )
            )
        rev = EvidenceRevision(
            attempt_id=attempt_id,
            position=position,
            file_id=file_id,
            prior_page_ids=prior,
            prior_hashes={p: receipt.page_hashes[p] for p in prior if p in receipt.page_hashes},
            actor_id=who.user.id,
            note=note.strip()[:500],
            created_at=now,
        )
        db.add(rev)
        record(
            db,
            actor=who.user.id,
            action="written.rescan_submitted",
            target_type="written_attempt",
            target_id=str(attempt_id),
            details={"position": position, "file": str(file_id), "sha256": sha, "post_cutoff": True},
        )
        db.commit()
    except BaseException:
        db.rollback()
        for key in keys:
            store.discard_uncommitted(key)
        raise
    db.refresh(rev)
    return rev


def confirm_unanswered(db: Session, who: Principal, attempt_id: uuid.UUID, position: int) -> None:
    """The learner confirms a seemingly blank answer was not attempted: zero under the rubric, maximum kept, and the
    question's unconsumed allowance released, as if declared unanswered before sealing (WA-AC62/82)."""
    from portal_api.modules.access import service as access
    from portal_api.modules.written import review

    attempt = _lock_attempt(db, attempt_id, who)
    now = _now(db)
    st = _requested_action(db, attempt_id, position, now)
    if st["learner_action"] != "confirm_or_rescan":
        raise Conflict("This question needs a clearer copy, not a confirmation.", code_reason="CONFIRM_NOT_OFFERED")
    form = db.get(WrittenForm, attempt.form_id)
    assert form is not None
    fi = next(f for f in form.items if f.position == position)
    rv = db.get(ContentVersion, fi.rubric_version_id)
    assert rv is not None
    rubric, _ = wq.parse_rubric(rv.body)
    assert rubric is not None
    case = _completion_case_for(db, attempt_id, position)
    review.publish_resolution(
        db,
        attempt_id,
        case=case,
        method="LEARNER",
        assessor_id=who.user.id,
        updates={str(position): {"status": "scored", "reason": "You confirmed you didn't answer this question."}},
        award_updates={
            str(position): {c.id: {"units": 0, "reason": "Not answered (confirmed)"} for c in rubric.criteria}
        },
        unit_updates={str(position): 0},
        reason=f"learner confirmed question {position} unanswered",
    )
    access.release_questions(db, attempt_id, [position], "learner confirmed unanswered after seal")
    record(
        db,
        actor=who.user.id,
        action="written.unanswered_confirmed",
        target_type="written_attempt",
        target_id=str(attempt_id),
        details={"position": position},
    )
    db.commit()


def _completion_case_for(db: Session, attempt_id: uuid.UUID, position: int) -> Any:
    from portal_api.modules.written import review

    for c in db.scalars(
        select(review.WrittenReviewCase).where(
            review.WrittenReviewCase.attempt_id == attempt_id,
            review.WrittenReviewCase.case_kind == "completion",
            review.WrittenReviewCase.status == "queued",
        )
    ):
        if position in (c.positions or []):
            return c
    raise Conflict("No open case covers this question.", code_reason="NO_OPEN_CASE")


def classify_for_decision(
    db: Session,
    who: Principal,
    case: Any,
    in_scope: set[str],
    classifications: dict[str, dict[str, Any]],
    now: datetime,
) -> None:
    """Called by the releasing decision: every unclassified revision of a question in scope gets a reviewed class and
    reason. A revision may only have been used as legible evidence if it is READABILITY (the reviewer's attestation)."""
    pending = [r for r in revisions_for(db, case.attempt_id, {int(p) for p in in_scope}) if r.classification is None]
    missing = [str(r.id) for r in pending if str(r.id) not in classifications]
    if missing:
        raise Unprocessable(
            "Classify each clearer copy (readability, new content or indeterminate) before releasing.",
            code_reason="REVISION_UNCLASSIFIED",
            errors=missing,
        )
    known = {str(r.id): r for r in pending}
    for rid, c in classifications.items():
        rev = known.get(rid)
        if rev is None:
            raise Unprocessable(f"Clearer copy {rid} isn't awaiting classification in this case.")
        cls = str(c.get("class", ""))
        reason = str(c.get("reason", "")).strip()
        if cls not in CLASSES:
            raise Unprocessable(f"Choose READABILITY, NEW_CONTENT or INDETERMINATE for {rid}.")
        if len(reason) < 5:
            raise Unprocessable(f"Give a reason for the classification of {rid}.")
        rev.classification = cls
        rev.class_reason = reason[:1000]
        rev.classified_by = who.user.id
        rev.classified_at = now
        rev.case_id = case.id
        record(
            db,
            actor=who.user.id,
            action="written.rescan_classified",
            target_type="written_attempt",
            target_id=str(case.attempt_id),
            details={"revision": rid, "class": cls, "position": rev.position},
        )


def expire_learner_actions(db: Session) -> int:
    """Deadline job: questions still awaiting the learner after 7 days, with no clearer copy awaiting review, are
    resolved unavailable and their allowance returned. Never a zero; audited; idempotent."""
    from portal_api.modules.access import service as access
    from portal_api.modules.written import review

    now = _now(db)
    done = 0
    candidates = db.scalars(
        select(review.WrittenReviewCase.attempt_id)
        .where(review.WrittenReviewCase.case_kind == "completion", review.WrittenReviewCase.status == "queued")
        .distinct()
    ).all()
    for attempt_id in candidates:
        db.scalar(select(WrittenAttempt.id).where(WrittenAttempt.id == attempt_id).with_for_update())
        current = review.released_result(db, attempt_id)
        if current is None:
            db.rollback()
            continue
        waiting = {r.position for r in revisions_for(db, attempt_id) if r.classification is None}
        overdue = sorted(
            int(p)
            for p, st in (current.question_status or {}).items()
            if st.get("status") == "pending"
            and st.get("learner_action")
            and now > datetime.fromisoformat(st["action_deadline"])
            and int(p) not in waiting
        )
        if not overdue:
            db.rollback()
            continue
        case = _completion_case_for(db, attempt_id, overdue[0])
        review.publish_resolution(
            db,
            attempt_id,
            case=case,
            method="SYSTEM",
            assessor_id=None,
            updates={
                str(p): {
                    "status": "unavailable",
                    "reason": "No clearer copy arrived within 7 days, so this question couldn't be assessed. "
                    "Its allowance was returned.",
                }
                for p in overdue
            },
            award_updates={},
            unit_updates={},
            reason="learner action deadline passed",
        )
        access.release_questions(db, attempt_id, overdue, "learner action deadline passed")
        record(
            db,
            actor=None,
            action="written.learner_action_expired",
            target_type="written_attempt",
            target_id=str(attempt_id),
            details={"positions": overdue},
        )
        db.commit()
        done += len(overdue)
    return done
