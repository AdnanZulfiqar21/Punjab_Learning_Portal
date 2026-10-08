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

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.exc import IntegrityError
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
        UniqueConstraint("attempt_id", "idempotency_key", name="uq_written_revision_key"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_attempt.id", ondelete="RESTRICT"), index=True)
    position: Mapped[int] = mapped_column(SmallInteger)
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_file.id", ondelete="RESTRICT"))
    prior_page_ids: Mapped[list[str]] = mapped_column(JSONB)  # the sealed pages this revision relates to
    prior_hashes: Mapped[dict[str, str]] = mapped_column(JSONB)  # page id -> sealed original file hash
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    note: Mapped[str] = mapped_column(Text, default="")
    # Always post-seal. Post-cutoff only if admitted after the attempt's pinned upload cutoff U (RS31-03); at exactly U
    # it is not post-cutoff, matching the admission rule "at or before U".
    post_cutoff: Mapped[bool] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # the post-lock admission time
    idempotency_key: Mapped[str] = mapped_column(String(80))  # RS31-01: exact retries return this revision
    request_hash: Mapped[str] = mapped_column(String(64))
    classification: Mapped[str | None] = mapped_column(String(14))
    class_reason: Mapped[str | None] = mapped_column(Text)
    classified_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    classified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("written_review_case.id", ondelete="RESTRICT"))


class LearnerObligation(Base):
    """RS31-02: one durable record per unresolved learner request on a question. Its deadline is set once, when first
    released, and survives action-type changes, omissions and repeated releases. Waiting on the learner and waiting on
    staff (a timely rescan not yet classified) are distinguished by `responded_at` and unclassified revisions."""

    __tablename__ = "written_learner_obligation"
    __table_args__ = (
        Index(
            "uq_written_obligation_open",
            "attempt_id",
            "position",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
        CheckConstraint("status in ('open','resolved')", name="written_obligation_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("written_attempt.id", ondelete="RESTRICT"), index=True)
    position: Mapped[int] = mapped_column(SmallInteger)
    action: Mapped[str] = mapped_column(String(20))  # the latest requested action (may change; the deadline doesn't)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(10), default="open")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution: Mapped[str | None] = mapped_column(String(30))


def open_obligation(db: Session, attempt_id: uuid.UUID, position: int) -> LearnerObligation | None:
    return db.scalar(
        select(LearnerObligation).where(
            LearnerObligation.attempt_id == attempt_id,
            LearnerObligation.position == position,
            LearnerObligation.status == "open",
        )
    )


def request_actions(
    db: Session, attempt_id: uuid.UUID, status: dict[str, dict[str, Any]], now: datetime, *, persist: bool
) -> None:
    """Give each requested learner action its durable deadline (creating the obligation on first release)."""
    from portal_api.modules.written.review import LEARNER_ACTION_WINDOW

    for pos, st in status.items():
        action = st.get("learner_action")
        if not action:
            continue
        ob = open_obligation(db, attempt_id, int(pos))
        if ob is None and persist:
            ob = LearnerObligation(
                attempt_id=attempt_id,
                position=int(pos),
                action=action,
                requested_at=now,
                deadline=now + LEARNER_ACTION_WINDOW,
            )
            db.add(ob)
        elif ob is not None and persist:
            ob.action = action  # changing the action never moves the deadline
        st["action_deadline"] = (ob.deadline if ob is not None else now + LEARNER_ACTION_WINDOW).isoformat()


def close_obligations(
    db: Session, attempt_id: uuid.UUID, status: dict[str, dict[str, Any]], now: datetime, resolution: str
) -> None:
    """Resolve open obligations for questions that are no longer pending."""
    for ob in db.scalars(
        select(LearnerObligation).where(LearnerObligation.attempt_id == attempt_id, LearnerObligation.status == "open")
    ):
        if status.get(str(ob.position), {}).get("status") != "pending":
            ob.status = "resolved"
            ob.resolved_at = now
            ob.resolution = resolution


def is_post_cutoff(admitted_at: datetime, upload_cutoff_at: datetime) -> bool:
    """Admission at or before U is within the window; only strictly later is post-cutoff (RS31-03)."""
    return admitted_at > upload_cutoff_at


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
    ob = open_obligation(db, attempt_id, position)
    deadline = ob.deadline if ob is not None else datetime.fromisoformat(st["action_deadline"])
    if now > deadline:
        raise Conflict("The 7 days to act on this question have passed.", code_reason="ACTION_DEADLINE_PASSED")
    return dict(st)


def revisions_for(db: Session, attempt_id: uuid.UUID, positions: set[int] | None = None) -> list[EvidenceRevision]:
    stmt = select(EvidenceRevision).where(EvidenceRevision.attempt_id == attempt_id)
    if positions is not None:
        stmt = stmt.where(EvidenceRevision.position.in_(positions))
    return list(db.scalars(stmt.order_by(EvidenceRevision.created_at)))


def _fingerprint(position: int, sha: str, note: str) -> str:
    return hashlib.sha256(f"{position}:{sha}:{note.strip()[:500]}".encode()).hexdigest()


def _by_key(db: Session, attempt_id: uuid.UUID, key: str) -> EvidenceRevision | None:
    return db.scalar(
        select(EvidenceRevision).where(
            EvidenceRevision.attempt_id == attempt_id, EvidenceRevision.idempotency_key == key
        )
    )


def _replay(rev: EvidenceRevision, fingerprint: str) -> EvidenceRevision:
    if rev.request_hash != fingerprint:
        raise Conflict("This request key was already used for a different copy.", code_reason="KEY_REUSED")
    return rev


def submit_rescan(
    db: Session,
    who: Principal,
    attempt_id: uuid.UUID,
    position: int,
    data: bytes,
    note: str,
    idempotency_key: str,
) -> tuple[EvidenceRevision, bool]:
    """Store a clearer copy of one pending answer as a linked revision. Returns (revision, replay).

    RS31-01: an exact retry with the same key returns the original revision (even after the deadline) and adds
    nothing; the same key with different content conflicts. Duplicate checks repeat under the attempt lock, and the
    one uniqueness race left is answered as a domain outcome. Only this request's unreferenced objects are removed.
    No connection is held while parsing or storing (DBHOLD-01)."""
    attempt = db.get(WrittenAttempt, attempt_id)
    if attempt is None or attempt.user_id != who.user.id:
        raise NotFound("Attempt not found.")
    sha = hashlib.sha256(data).hexdigest()
    fingerprint = _fingerprint(position, sha, note)
    if (prior := _by_key(db, attempt_id, idempotency_key)) is not None:
        return _replay(prior, fingerprint), True
    if attempt.status != "sealed":
        raise Conflict("Rescans are for submitted scripts.")
    _requested_action(db, attempt_id, position, _now(db))
    if len(revisions_for(db, attempt_id, {position})) >= MAX_REVISIONS_PER_QUESTION:
        raise Conflict(
            f"You can send at most {MAX_REVISIONS_PER_QUESTION} clearer copies of one answer.",
            code_reason="RESCAN_LIMIT",
        )
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
        # Everything decided above is decided again under the lock.
        if (prior := _by_key(db, attempt_id, idempotency_key)) is not None:
            db.rollback()
            for key in keys:
                store.discard_uncommitted(key)
            return _replay(prior, fingerprint), True
        _requested_action(db, attempt_id, position, now)
        if len(revisions_for(db, attempt_id, {position})) >= MAX_REVISIONS_PER_QUESTION:
            raise Conflict("Too many clearer copies for this answer.", code_reason="RESCAN_LIMIT")
        if db.scalar(select(WrittenFile.id).where(WrittenFile.attempt_id == attempt_id, WrittenFile.sha256 == sha)):
            raise Conflict("This copy was already received.", code_reason="SAME_FILE")
        receipt = db.scalar(select(WrittenReceipt).where(WrittenReceipt.attempt_id == attempt_id))
        assert receipt is not None
        slots = receipt.manifest.get("slots", {})
        prior_pages = sorted(
            {p for k, v in slots.items() if k.split(":")[0] == str(position) for p in v.get("pages", [])}
        )
        late = is_post_cutoff(now, attempt.upload_cutoff_at)
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
            prior_page_ids=prior_pages,
            prior_hashes={p: receipt.page_hashes[p] for p in prior_pages if p in receipt.page_hashes},
            actor_id=who.user.id,
            note=note.strip()[:500],
            post_cutoff=late,
            created_at=now,
            idempotency_key=idempotency_key,
            request_hash=fingerprint,
        )
        db.add(rev)
        ob = open_obligation(db, attempt_id, position)
        if ob is not None and ob.responded_at is None:
            ob.responded_at = now  # the learner answered in time; now waiting on staff
        record(
            db,
            actor=who.user.id,
            action="written.rescan_submitted",
            target_type="written_attempt",
            target_id=str(attempt_id),
            details={
                "position": position,
                "file": str(file_id),
                "sha256": sha,
                "admitted_at": now.isoformat(),
                "upload_cutoff_at": attempt.upload_cutoff_at.isoformat(),
                "post_cutoff": late,
                "post_seal": True,
            },
        )
        db.flush()
        db.commit()
    except IntegrityError as e:
        db.rollback()
        for key in keys:
            store.discard_uncommitted(key)
        constraint = getattr(getattr(e.orig, "diag", None), "constraint_name", None)
        if constraint == "uq_written_revision_key":
            prior = _by_key(db, attempt_id, idempotency_key)
            if prior is not None:
                return _replay(prior, fingerprint), True
        if constraint == "uq_written_file_attempt_hash":
            raise Conflict("This copy was already received.", code_reason="SAME_FILE") from e
        raise
    except BaseException:
        db.rollback()
        for key in keys:
            store.discard_uncommitted(key)
        raise
    db.refresh(rev)
    return rev, False


def confirm_unanswered(db: Session, who: Principal, attempt_id: uuid.UUID, position: int) -> None:
    """The learner confirms a seemingly blank answer was not attempted: zero under the rubric, maximum kept, and the
    question's unconsumed allowance released, as if declared unanswered before sealing (WA-AC62/82)."""
    from portal_api.modules.access import service as access
    from portal_api.modules.written import review

    attempt = _lock_attempt(db, attempt_id, who)
    now = _now(db)
    done = db.scalar(
        select(LearnerObligation).where(
            LearnerObligation.attempt_id == attempt_id,
            LearnerObligation.position == position,
            LearnerObligation.resolution == "confirmed_unanswered",
        )
    )
    if done is not None:  # RS31-01: a repeated confirmation is answered without a second resolution
        db.rollback()
        return
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
    ob = open_obligation(db, attempt_id, position)
    if ob is not None:
        ob.status, ob.resolved_at, ob.resolution = "resolved", now, "confirmed_unanswered"
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


def evidence_for_decision(
    db: Session, attempt_id: uuid.UUID, evidence: dict[str, list[str]], scored: set[str]
) -> dict[str, list[dict[str, str]]]:
    """Section 4 (PR #31 review): which clearer copies supplied each marked answer. Only READABILITY revisions of the
    same attempt and question may be named, and only for questions this decision scores. Questions not named here were
    marked from the sealed original, which stays possible even when another copy is NEW_CONTENT or INDETERMINATE."""
    out: dict[str, list[dict[str, str]]] = {}
    for pos, ids in evidence.items():
        if pos not in scored:
            raise Unprocessable(
                f"Question {pos} isn't being marked in this decision, so it can't name evidence.",
                code_reason="EVIDENCE_NOT_ELIGIBLE",
            )
        entries = []
        for rid in dict.fromkeys(ids):
            try:
                rev = db.get(EvidenceRevision, uuid.UUID(rid))
            except ValueError:
                rev = None
            if rev is None or rev.attempt_id != attempt_id or str(rev.position) != pos:
                raise Unprocessable(
                    f"Copy {rid} doesn't belong to question {pos}.", code_reason="EVIDENCE_NOT_ELIGIBLE"
                )
            if rev.classification != "READABILITY":
                raise Unprocessable(
                    f"Copy {rid} is classified {rev.classification or 'not yet'}; only a READABILITY copy may be used.",
                    code_reason="EVIDENCE_NOT_ELIGIBLE",
                )
            f = db.get(WrittenFile, rev.file_id)
            assert f is not None
            entries.append({"id": str(rev.id), "file_id": str(f.id), "sha256": f.sha256})
        if entries:
            out[pos] = entries
    return out


def expire_learner_actions(db: Session) -> int:
    """Deadline job: open obligations past their durable deadline, whose question is still pending and with no
    timely clearer copy awaiting review, are resolved unavailable with allowance returned. Never a zero; idempotent."""
    from portal_api.modules.access import service as access
    from portal_api.modules.written import review

    now = _now(db)
    done = 0
    attempts = db.scalars(
        select(LearnerObligation.attempt_id)
        .where(LearnerObligation.status == "open", LearnerObligation.deadline < now)
        .distinct()
    ).all()
    for attempt_id in attempts:
        db.scalar(select(WrittenAttempt.id).where(WrittenAttempt.id == attempt_id).with_for_update())
        current = review.released_result(db, attempt_id)
        if current is None:
            db.rollback()
            continue
        waiting_on_staff = {r.position for r in revisions_for(db, attempt_id) if r.classification is None}
        overdue = sorted(
            ob.position
            for ob in db.scalars(
                select(LearnerObligation).where(
                    LearnerObligation.attempt_id == attempt_id,
                    LearnerObligation.status == "open",
                    LearnerObligation.deadline < now,
                )
            )
            if (current.question_status or {}).get(str(ob.position), {}).get("status") == "pending"
            and ob.position not in waiting_on_staff
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
        for ob in db.scalars(
            select(LearnerObligation).where(
                LearnerObligation.attempt_id == attempt_id,
                LearnerObligation.status == "open",
                LearnerObligation.position.in_(overdue),
            )
        ):
            ob.status, ob.resolved_at, ob.resolution = "resolved", now, "deadline_unavailable"
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


def repair_post_cutoff_flags(db: Session) -> list[str]:
    """RS31-03 repair: revisions recorded post-cutoff although admitted at or before the attempt's upload cutoff.
    Corrects the derived flag and audits old and new values; evidence and ledger are untouched. Idempotent."""
    fixed = []
    rows = db.execute(
        select(EvidenceRevision, WrittenAttempt.upload_cutoff_at)
        .join(WrittenAttempt, WrittenAttempt.id == EvidenceRevision.attempt_id)
        .where(EvidenceRevision.post_cutoff.is_(True), EvidenceRevision.created_at <= WrittenAttempt.upload_cutoff_at)
    ).all()
    for rev, cutoff in rows:
        rev.post_cutoff = False
        record(
            db,
            actor=None,
            action="written.revision_flag_corrected",
            target_type="written_evidence_revision",
            target_id=str(rev.id),
            details={
                "field": "post_cutoff",
                "old": True,
                "new": False,
                "admitted_at": rev.created_at.isoformat(),
                "upload_cutoff_at": cutoff.isoformat(),
                "finding": "RS31-03",
            },
        )
        fixed.append(str(rev.id))
    db.commit()
    return fixed
