"""Written practice: forms, attempts, evidence upload, mapping and sealing (W03/W04, §20.7.2).

Write paths follow the MCQ discipline: bounded validation first, then lock the attempt row and read the database clock
*after* the lock; admission at or before U is eligible, after U refused. Sealing pre-validates every referenced object
(server-side hash re-check) outside the lock, then rechecks status, revision and completeness under it and commits one
receipt. Exact retries return the original receipt even after U; a changed payload with the same key conflicts.
Nothing is assessed before sealing, and an unsealed attempt is never partially sealed on timeout.
"""

from __future__ import annotations

import hashlib
import json
import random
import secrets
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from portal_api.errors import Conflict, NotFound, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.content import written as wq
from portal_api.modules.content.models import Availability, ContentItem, ContentVersion
from portal_api.modules.content.workflow import roles_in_scope
from portal_api.modules.curriculum.models import BookEdition, Chapter, Grade, Subject
from portal_api.modules.identity.deps import Principal
from portal_api.modules.identity.models import StaffRoleGrant
from portal_api.modules.identity.permissions import Permission, Role, permissions_for
from portal_api.modules.written import storage, validate
from portal_api.modules.written.models import (
    WrittenAttempt,
    WrittenForm,
    WrittenFormItem,
    WrittenPage,
    WrittenReceipt,
)

UPLOAD_ALLOWANCE_S = 10 * 60  # proposed G for chapter practice (§20.7.2); pinned per form and disclosed before start
UNTIMED_PERMIT_S = 24 * 60 * 60  # untimed practice still has a finite upload permit
CAPS = {
    "max_pages": 10,
    "max_total_bytes": 60 * 1024 * 1024,
    "image_bytes": validate.IMAGE_MAX_BYTES,
    "pdf_bytes": validate.PDF_MAX_BYTES,
}


def db_now(db: Session) -> datetime:
    now: datetime = db.execute(select(func.clock_timestamp())).scalar_one()
    return now


def slot_key(position: int, subpart: str | None) -> str:
    return f"{position}:{subpart or '*'}"


# ------------------------------------------------------------------ pool and availability
def _live_rubric_versions(db: Session, items: list[ContentItem]) -> dict[uuid.UUID, ContentVersion]:
    """Published rubric version per written item, matching the item's published question version."""
    if not items:
        return {}
    rows = db.execute(
        select(ContentItem, ContentVersion)
        .join(ContentVersion, ContentVersion.id == ContentItem.published_version_id)
        .where(
            ContentItem.kind == "rubric",
            ContentItem.availability == Availability.live.value,
            ContentItem.parent_item_id.in_([i.id for i in items]),
        )
    ).all()
    by_parent: dict[uuid.UUID, ContentVersion] = {}
    published = {i.id: i.published_version_id for i in items}
    for rubric, rv in rows:
        assert rubric.parent_item_id is not None
        if str(rv.body.get("question_version_id")) == str(published[rubric.parent_item_id]):
            by_parent[rubric.parent_item_id] = rv
    return by_parent


def _pool(
    db: Session, grade: int, subject: str, chapter_ids: list[uuid.UUID], question_type: str
) -> dict[uuid.UUID, list[tuple[ContentItem, ContentVersion, ContentVersion]]]:
    rows = db.execute(
        select(ContentItem, ContentVersion)
        .join(ContentVersion, ContentVersion.id == ContentItem.published_version_id)
        .where(
            ContentItem.kind == "written",
            ContentItem.availability == Availability.live.value,
            ContentItem.grade_number == grade,
            ContentItem.subject_code == subject,
            ContentItem.chapter_id.in_(chapter_ids),
        )
    ).all()
    rubrics = _live_rubric_versions(db, [i for i, _ in rows])
    families: dict[uuid.UUID, list[tuple[ContentItem, ContentVersion, ContentVersion]]] = defaultdict(list)
    for item, qv in rows:
        if item.id not in rubrics:
            continue  # never offer a question without a published rubric for its exact version
        if question_type != "mixed" and qv.body.get("question_type") != question_type:
            continue
        families[item.family_id or item.id].append((item, qv, rubrics[item.id]))
    return families


def review_staffed(db: Session, grade: int, subject: str) -> bool:
    """Is there at least one teacher reviewer for this class and subject (§20.4: no unstaffed review route)?"""
    users = db.scalars(
        select(StaffRoleGrant.user_id).where(
            StaffRoleGrant.revoked_at.is_(None),
            StaffRoleGrant.role.in_([Role.subject_reviewer.value, Role.academic_adjudicator.value]),
        )
    ).all()
    return any(
        Permission.review_content in permissions_for(roles_in_scope(db, uid, grade, subject)) for uid in set(users)
    )


def _chapters(db: Session, grade: int, subject: str) -> list[Chapter]:
    return list(
        db.scalars(
            select(Chapter)
            .join(BookEdition, BookEdition.id == Chapter.book_id)
            .join(Grade, Grade.id == BookEdition.grade_id)
            .join(Subject, Subject.id == BookEdition.subject_id)
            .where(Grade.number == grade, Subject.code == subject, Subject.active, Chapter.retired_at.is_(None))
            .order_by(Chapter.display_order)
        )
    )


def availability(db: Session, grade: int, subject: str) -> dict[str, Any]:
    chapters = _chapters(db, grade, subject)
    if not chapters:
        raise NotFound("No book is available for this class and subject.")
    pool = _pool(db, grade, subject, [c.id for c in chapters], "mixed")
    per_chapter: dict[uuid.UUID, int] = defaultdict(int)
    for members in pool.values():
        per_chapter[members[0][0].chapter_id] += 1
    return {
        "review_staffed": review_staffed(db, grade, subject),
        "upload_allowance_s": UPLOAD_ALLOWANCE_S,
        "caps": CAPS,
        "chapters": [
            {"chapter_id": c.id, "number": c.number, "title": c.title, "questions": per_chapter.get(c.id, 0)}
            for c in chapters
        ],
    }


# ------------------------------------------------------------------ forms and attempts
def create_form(
    db: Session,
    who: Principal,
    *,
    idempotency_key: str,
    grade: int,
    subject: str,
    chapter_ids: list[uuid.UUID],
    question_type: str,
    question_count: int,
    writing_minutes: int | None,
) -> WrittenForm:
    req = {
        "grade": grade,
        "subject": subject,
        "chapter_ids": sorted(map(str, chapter_ids)),
        "question_type": question_type,
        "question_count": question_count,
        "writing_minutes": writing_minutes,
    }
    rhash = hashlib.sha256(json.dumps(req, sort_keys=True).encode()).hexdigest()
    existing = db.scalar(
        select(WrittenForm).where(WrittenForm.owner_id == who.user.id, WrittenForm.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.request_hash != rhash:
            raise Conflict("This request key was already used for a different test.")
        return existing
    valid = {c.id for c in _chapters(db, grade, subject)}
    if not chapter_ids or not set(chapter_ids) <= valid:
        raise Unprocessable("Choose chapters from this class and subject's book.")
    if not review_staffed(db, grade, subject):
        raise Unprocessable(
            "Written practice for this subject isn't offered yet: no teacher reviewer is available to mark it."
        )
    pool = _pool(db, grade, subject, chapter_ids, question_type)
    if len(pool) < question_count:
        raise Unprocessable(
            f"Only {len(pool)} reviewed written question(s) are available for this selection.",
            available=len(pool),
            requested=question_count,
        )
    seed = secrets.randbits(62)
    rng = random.Random(seed)  # noqa: S311 - reproducible sampling from a stored seed, not a secret
    chosen = rng.sample(sorted(pool, key=str), question_count)
    form = WrittenForm(
        id=uuid.uuid4(),
        owner_id=who.user.id,
        idempotency_key=idempotency_key,
        request_hash=rhash,
        grade_number=grade,
        subject_code=subject,
        scope={"chapter_ids": req["chapter_ids"]},
        seed=seed,
        question_type=question_type,
        writing_s=writing_minutes * 60 if writing_minutes else None,
        upload_allowance_s=UPLOAD_ALLOWANCE_S if writing_minutes else UNTIMED_PERMIT_S,
        caps=CAPS,
        max_units=0,
    )
    db.add(form)
    total = 0
    for position, family in enumerate(chosen, start=1):
        item, qv, rv = rng.choice(sorted(pool[family], key=lambda t: str(t[0].id)))
        q, _ = wq.parse_written(qv.body)
        assert q is not None
        slots = [slot_key(position, s) for s in wq.subpart_maxima(q)]
        total += q.max_units
        db.add(
            WrittenFormItem(
                form_id=form.id,
                position=position,
                item_id=item.id,
                family_id=family,
                question_version_id=qv.id,
                rubric_version_id=rv.id,
                max_units=q.max_units,
                slots=slots,
            )
        )
    form.max_units = total
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        winner = db.scalar(
            select(WrittenForm).where(
                WrittenForm.owner_id == who.user.id, WrittenForm.idempotency_key == idempotency_key
            )
        )
        if winner is None or winner.request_hash != rhash:
            raise Conflict("This request key was already used for a different test.") from None
        return winner
    db.refresh(form)
    return form


def start(db: Session, who: Principal, form_id: uuid.UUID) -> WrittenAttempt:
    form = db.get(WrittenForm, form_id)
    if form is None or form.owner_id != who.user.id:
        raise NotFound("Test not found.")
    existing = db.scalar(
        select(WrittenAttempt).where(WrittenAttempt.form_id == form_id, WrittenAttempt.user_id == who.user.id)
    )
    if existing is not None:
        return existing
    now = db_now(db)
    deadline = now + timedelta(seconds=form.writing_s) if form.writing_s else None
    cutoff = (deadline or now) + timedelta(seconds=form.upload_allowance_s)
    db.execute(
        insert(WrittenAttempt)
        .values(
            id=uuid.uuid4(),
            form_id=form.id,
            user_id=who.user.id,
            status="active",
            started_at=now,
            writing_deadline_at=deadline,
            upload_allowance_s=form.upload_allowance_s,
            upload_cutoff_at=cutoff,
            manifest={"slots": {}},
            manifest_revision=0,
        )
        .on_conflict_do_nothing(constraint="uq_written_attempt_form_user")
    )
    db.commit()
    attempt = db.scalar(
        select(WrittenAttempt).where(WrittenAttempt.form_id == form_id, WrittenAttempt.user_id == who.user.id)
    )
    assert attempt is not None
    return attempt


def _lock(db: Session, attempt_id: uuid.UUID, who: Principal) -> WrittenAttempt:
    attempt = db.scalar(select(WrittenAttempt).where(WrittenAttempt.id == attempt_id).with_for_update())
    if attempt is None or attempt.user_id != who.user.id:
        raise NotFound("Attempt not found.")
    return attempt


def _expire_if_due(db: Session, attempt: WrittenAttempt, now: datetime) -> bool:
    if attempt.status == "active" and now > attempt.upload_cutoff_at:
        attempt.status = "expired"
        attempt.expired_at = now
        record(
            db,
            actor=None,
            action="written.expired",
            target_type="written_attempt",
            target_id=str(attempt.id),
            details={"pages": len(_pages(db, attempt.id)), "manifest_revision": attempt.manifest_revision},
        )
        return True
    return False


def _pages(db: Session, attempt_id: uuid.UUID) -> list[WrittenPage]:
    return list(
        db.scalars(
            select(WrittenPage)
            .where(WrittenPage.attempt_id == attempt_id, WrittenPage.status == "uploaded")
            .order_by(WrittenPage.uploaded_at, WrittenPage.id)
        )
    )


def _require_open(attempt: WrittenAttempt) -> None:
    if attempt.status == "sealed":
        raise Conflict("This answer script has been submitted and can't be changed.", attempt_status=attempt.status)
    if attempt.status == "expired":
        raise Conflict(
            "The upload window has closed. Pages you uploaded are kept but weren't submitted.",
            attempt_status=attempt.status,
        )


def load(db: Session, who: Principal, attempt_id: uuid.UUID) -> WrittenAttempt:
    attempt = _lock(db, attempt_id, who)
    _expire_if_due(db, attempt, db_now(db))
    db.commit()
    db.refresh(attempt)
    return attempt


# ------------------------------------------------------------------ evidence
def upload_page(db: Session, who: Principal, attempt_id: uuid.UUID, data: bytes) -> tuple[WrittenPage, bool, list[str]]:
    """Validate (bounded, before the lock), then admit under the lock. Returns (page, duplicate, warnings)."""
    try:
        checked = validate.check(data)
    except validate.Rejected as e:
        raise Unprocessable(e.reason, code_reason="UNSUPPORTED_FILE") from e
    sha = hashlib.sha256(data).hexdigest()
    attempt = _lock(db, attempt_id, who)
    now = db_now(db)
    if _expire_if_due(db, attempt, now):
        db.commit()
    _require_open(attempt)
    existing = db.scalar(select(WrittenPage).where(WrittenPage.attempt_id == attempt.id, WrittenPage.sha256 == sha))
    if existing is not None:
        db.commit()
        return existing, True, checked.warnings  # exact duplicate within this attempt only: reuse, never re-store
    pages = _pages(db, attempt.id)
    caps = attempt.form.caps
    if len(pages) >= caps["max_pages"]:
        raise Unprocessable(f"An answer script can have at most {caps['max_pages']} files.")
    if sum(p.size for p in pages) + len(data) > caps["max_total_bytes"]:
        raise Unprocessable(f"The script would exceed {caps['max_total_bytes'] // (1024 * 1024)} MB in total.")
    page_id = uuid.uuid4()
    stored = storage.get_store().put(f"{attempt.id}/{page_id}", data)
    assert stored.sha256 == sha
    page = WrittenPage(
        id=page_id,
        attempt_id=attempt.id,
        storage_key=stored.key,
        sha256=sha,
        size=stored.size,
        content_type=checked.content_type,
        width=checked.width,
        height=checked.height,
        pdf_pages=checked.pages,
        uploaded_at=now,
    )
    db.add(page)
    attempt.manifest = {**attempt.manifest, "order": [*attempt.manifest.get("order", []), str(page_id)]}
    db.commit()
    db.refresh(page)
    return page, False, checked.warnings


def page_bytes(db: Session, who: Principal, attempt_id: uuid.UUID, page_id: uuid.UUID) -> tuple[bytes, str]:
    attempt = db.get(WrittenAttempt, attempt_id)
    page = db.get(WrittenPage, page_id)
    if attempt is None or attempt.user_id != who.user.id or page is None or page.attempt_id != attempt.id:
        raise NotFound("Page not found.")
    return storage.get_store().get(page.storage_key), page.content_type


def update_manifest(
    db: Session, who: Principal, attempt_id: uuid.UUID, *, expected_revision: int, slots: dict[str, dict[str, Any]]
) -> WrittenAttempt:
    attempt = _lock(db, attempt_id, who)
    now = db_now(db)
    if _expire_if_due(db, attempt, now):
        db.commit()
    _require_open(attempt)
    if expected_revision != attempt.manifest_revision:
        raise Conflict(
            "Your answer mapping changed on another device. Review the latest version before saving again.",
            current={"revision": attempt.manifest_revision, "manifest": attempt.manifest},
        )
    allowed = {s for fi in attempt.form.items for s in fi.slots}
    pages = {str(p.id) for p in _pages(db, attempt.id)}
    errors = []
    clean: dict[str, dict[str, Any]] = {}
    for key, value in slots.items():
        if key not in allowed:
            errors.append(f"Unknown answer slot {key}.")
            continue
        ids = [str(x) for x in value.get("pages", [])]
        unanswered = bool(value.get("unanswered", False))
        if unanswered and ids:
            errors.append(f"Slot {key} can't be both answered and declared unanswered.")
        if set(ids) - pages:
            errors.append(f"Slot {key} refers to pages that aren't part of this script.")
        clean[key] = {"pages": list(dict.fromkeys(ids)), "unanswered": unanswered}
    if errors:
        raise Unprocessable("The mapping isn't valid.", errors=errors)
    attempt.manifest = {**attempt.manifest, "slots": clean}
    attempt.manifest_revision += 1
    db.commit()
    db.refresh(attempt)
    return attempt


# ------------------------------------------------------------------ seal
def seal(
    db: Session, who: Principal, attempt_id: uuid.UUID, *, idempotency_key: str, expected_revision: int
) -> tuple[WrittenReceipt, bool]:
    rhash = hashlib.sha256(json.dumps({"revision": expected_revision}).encode()).hexdigest()
    attempt = db.get(WrittenAttempt, attempt_id)
    if attempt is None or attempt.user_id != who.user.id:
        raise NotFound("Attempt not found.")
    prior = db.scalar(select(WrittenReceipt).where(WrittenReceipt.attempt_id == attempt.id))
    if prior is not None:
        if prior.idempotency_key == idempotency_key and prior.request_hash == rhash:
            return prior, True  # exact retry: the original receipt, even after U
        if prior.idempotency_key == idempotency_key:
            raise Conflict("This submission key was already used with different contents.")
        raise Conflict("This answer script was already submitted.", receipt_id=str(prior.id))

    # Pre-validate referenced objects outside the admission transaction (bounded I/O, no lock held).
    store = storage.get_store()
    referenced = {p for slot in attempt.manifest.get("slots", {}).values() for p in slot.get("pages", [])}
    verified: dict[str, str] = {}
    for page in _pages(db, attempt.id):
        if str(page.id) in referenced:
            if store.sha256(page.storage_key) != page.sha256:
                raise Conflict(f"An uploaded page failed its integrity check; upload it again ({page.id}).")
            verified[str(page.id)] = page.sha256
    db.rollback()  # release the read snapshot before taking the lock

    attempt = _lock(db, attempt_id, who)
    now = db_now(db)
    prior = db.scalar(select(WrittenReceipt).where(WrittenReceipt.attempt_id == attempt.id))
    if prior is not None:  # a concurrent seal won while we were pre-validating
        db.rollback()
        return seal(db, who, attempt_id, idempotency_key=idempotency_key, expected_revision=expected_revision)
    if _expire_if_due(db, attempt, now):
        db.commit()
        raise Conflict(
            "The upload window closed before this submission was admitted. Nothing was submitted.",
            attempt_status="expired",
        )
    _require_open(attempt)
    if expected_revision != attempt.manifest_revision:
        raise Conflict(
            "Your answer mapping changed; review it and submit again.",
            current={"revision": attempt.manifest_revision, "manifest": attempt.manifest},
        )
    slots = attempt.manifest.get("slots", {})
    missing = [
        s
        for fi in attempt.form.items
        for s in fi.slots
        if not (slots.get(s, {}).get("pages") or slots.get(s, {}).get("unanswered"))
    ]
    if missing:
        raise Unprocessable("Give every answer at least one page, or mark it as not answered.", missing=missing)
    live_ids = {str(p.id) for p in _pages(db, attempt.id)}
    used = {p for s in slots.values() for p in s.get("pages", [])}
    if used - live_ids or used - set(verified):
        raise Conflict("Some mapped pages changed while submitting; review the mapping and submit again.")
    receipt = WrittenReceipt(
        attempt_id=attempt.id,
        idempotency_key=idempotency_key,
        request_hash=rhash,
        admitted_at=now,
        manifest_revision=attempt.manifest_revision,
        manifest=attempt.manifest,
        page_hashes={p: verified[p] for p in sorted(used)},
        answered_slots=sum(1 for s in slots.values() if s.get("pages")),
        unanswered_slots=sum(1 for s in slots.values() if s.get("unanswered")),
    )
    db.add(receipt)
    attempt.status = "sealed"
    attempt.sealed_at = now
    record(
        db,
        actor=who.user.id,
        action="written.sealed",
        target_type="written_attempt",
        target_id=str(attempt.id),
        details={"revision": attempt.manifest_revision, "pages": len(used), "admitted_at": now.isoformat()},
    )
    db.commit()
    db.refresh(receipt)
    return receipt, False


def expire_due(db: Session, limit: int = 200) -> int:
    done = 0
    ids = db.scalars(
        select(WrittenAttempt.id)
        .where(WrittenAttempt.status == "active", WrittenAttempt.upload_cutoff_at < func.now())
        .limit(limit)
    ).all()
    for attempt_id in ids:
        attempt = db.scalar(
            select(WrittenAttempt).where(WrittenAttempt.id == attempt_id).with_for_update(skip_locked=True)
        )
        if attempt is not None and _expire_if_due(db, attempt, db_now(db)):
            done += 1
        db.commit()
    return done


def receipt_for(db: Session, attempt_id: uuid.UUID) -> WrittenReceipt | None:
    return db.scalar(select(WrittenReceipt).where(WrittenReceipt.attempt_id == attempt_id))


def pages_of(db: Session, attempt_id: uuid.UUID) -> list[WrittenPage]:
    return _pages(db, attempt_id)
