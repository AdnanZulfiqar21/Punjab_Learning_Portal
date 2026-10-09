"""Editorial workflow (P06.S1.T2/T3, P06.S3.T2/T3).

    draft ──submit──▶ submitted ──approve──▶ approved ──publish──▶ published
      ▲  ◀──withdraw──┘   │                                         │  ▲
      └──── edit ◀── changes_requested ◀──request changes           │  └── release ── quarantined ◀── quarantine
                                                                    └── revise (new draft version, reason required)
Learner availability is separate from editorial state: unpublished → live ⇄ quarantined, any → retired (hidden, never
deleted). A revision can be drafted while the previous version stays live or quarantined; publishing a corrected
version makes the item live again.

Rules enforced here, server-side, for every caller:
* Authors, reviewers and publishers act only inside the grade/subject scope of their role grant.
* Independent review: nobody who edited a version may approve or publish it.
* Edits are optimistic: a save names the revision it started from; a stale save gets 409 with the current text.
* Submission needs valid blocks and at least one source page reference to the chapter's own textbook.
* Publication additionally needs: an approval, renderer compatibility (§5.4) and CONFIRMED publication rights for every
  referenced source. Missing reviewers or rights block publication only, never drafting or review (BLOCKERS scope rule).
* Every transition is audited in the same transaction.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.errors import Conflict, Forbidden, NotFound, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.content import blocks, kinds, links
from portal_api.modules.content.models import (
    Availability,
    ContentItem,
    ContentVersion,
    ItemState,
    ReviewDecision,
    VersionStatus,
)
from portal_api.modules.curriculum.models import BookEdition, Chapter, SourceDocument, Subject, Topic
from portal_api.modules.identity.deps import Principal
from portal_api.modules.identity.models import AppUser, StaffRoleGrant
from portal_api.modules.identity.permissions import Permission, Role, permissions_for


def _now() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------------ scope
def roles_in_scope(db: Session, user_id: uuid.UUID, grade: int, subject: str) -> set[Role]:
    """Roles the user holds that cover this grade and subject. A grant's scope may list `grades` and/or `subjects`;
    a missing key means unrestricted on that axis."""
    held: set[Role] = set()
    for grant in db.scalars(
        select(StaffRoleGrant).where(StaffRoleGrant.user_id == user_id, StaffRoleGrant.revoked_at.is_(None))
    ):
        scope = grant.scope or {}
        grades = scope.get("grades")
        subjects = scope.get("subjects")
        if grades is not None and grade not in grades:
            continue
        if subjects is not None and subject not in subjects:
            continue
        held.add(Role(grant.role))
    return held


def scope_clause(db: Session, user_id: uuid.UUID, roles: set[Role]) -> Any:
    """SQL filter for items inside the user's grants of `roles` (one query for grants, applied before LIMIT).
    Returns True for unrestricted access and False when the user holds none of the roles."""
    from sqlalchemy import and_, false, or_, true

    clauses = []
    for grant in db.scalars(
        select(StaffRoleGrant).where(
            StaffRoleGrant.user_id == user_id,
            StaffRoleGrant.revoked_at.is_(None),
            StaffRoleGrant.role.in_([r.value for r in roles]),
        )
    ):
        scope = grant.scope or {}
        grades, subjects = scope.get("grades"), scope.get("subjects")
        if grades is None and subjects is None:
            return true()
        parts = []
        if grades is not None:
            parts.append(ContentItem.grade_number.in_(grades))
        if subjects is not None:
            parts.append(ContentItem.subject_code.in_(subjects))
        clauses.append(and_(*parts))
    return or_(*clauses) if clauses else false()


def _require_scoped(db: Session, who: Principal, permission: Permission, item: ContentItem) -> None:
    perms = permissions_for(roles_in_scope(db, who.user.id, item.grade_number, item.subject_code))
    if permission not in perms:
        raise Forbidden("This item is outside the subjects and classes your role covers.")


# ------------------------------------------------------------------ source references
class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_document_id: uuid.UUID
    pdf_from: int = Field(ge=1)
    pdf_to: int = Field(ge=1)
    note: str | None = Field(default=None, max_length=300)


def check_sources(db: Session, chapter: Chapter, refs: object) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    """Validate source page references. Returns (errors, warnings, normalised refs)."""
    if not isinstance(refs, list):
        return ["source_refs must be a list."], [], []
    errors: list[str] = []
    warnings: list[str] = []
    out: list[dict[str, Any]] = []
    book = db.get(BookEdition, chapter.book_id)
    assert book is not None
    for i, raw in enumerate(refs):
        try:
            ref = SourceRef.model_validate(raw)
        except ValidationError as e:
            errors += [f"source_refs[{i}].{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()]
            continue
        doc = db.get(SourceDocument, ref.source_document_id)
        if doc is None:
            errors.append(f"source_refs[{i}]: unknown source document.")
            continue
        if doc.id != book.source_document_id:
            errors.append(
                f"source_refs[{i}]: must reference this chapter's own textbook ({book.title or doc.source_id})."
            )
            continue
        if ref.pdf_from > ref.pdf_to or ref.pdf_to > doc.pdf_pages:
            errors.append(f"source_refs[{i}]: PDF pages must be within 1 to {doc.pdf_pages} and in order.")
            continue
        if chapter.pdf_start and chapter.pdf_end and (ref.pdf_from < chapter.pdf_start or ref.pdf_to > chapter.pdf_end):
            warnings.append(
                f"source_refs[{i}]: pages {ref.pdf_from} to {ref.pdf_to} fall outside this chapter "
                f"(PDF {chapter.pdf_start} to {chapter.pdf_end})."
            )
        missing = {int(p) for p in (doc.missing_pages or []) if isinstance(p, int | str) and str(p).isdigit()}
        if missing & set(range(ref.pdf_from, ref.pdf_to + 1)):
            warnings.append(f"source_refs[{i}]: the range includes pages recorded as missing from the source.")
        out.append(ref.model_dump(mode="json"))
    return errors, warnings, out


def _validate(db: Session, item: ContentItem, version: ContentVersion, *, for_publication: bool) -> dict[str, Any]:
    chapter = db.get(Chapter, item.chapter_id)
    assert chapter is not None
    result = kinds.get(item.kind).validate(version.body, for_publication)
    s_err, s_warn, _ = check_sources(db, chapter, version.source_refs)
    errors = result.errors + s_err + links.check(db, item, version, for_publication=for_publication)
    warnings = result.warnings + s_warn
    if not version.source_refs:
        errors.append("Add at least one source page reference.")
    if for_publication:
        if chapter.retired_at is not None:
            errors.append("The chapter has been retired from the catalogue.")
        for ref in version.source_refs:
            doc = db.get(SourceDocument, uuid.UUID(ref["source_document_id"]))
            if doc is not None and doc.publication_rights != "CONFIRMED":
                errors.append(
                    f"Publication rights for {doc.source_id} are {doc.publication_rights}; the owner must confirm them "
                    "before derived material can be published."
                )
                break
    return {"ok": not errors, "errors": errors, "warnings": warnings, "block_types": result.block_types}


validate_version = _validate


def validate_draft(
    db: Session, chapter_id: uuid.UUID, body: object, refs: object, for_publication: bool, kind: str = "lesson"
) -> dict[str, Any]:
    """Dry validation for the editor (nothing is written)."""
    chapter = _active_chapter(db, chapter_id)
    result = kinds.get(kind).validate(body, for_publication)
    s_err, s_warn, _ = check_sources(db, chapter, refs)
    errors = result.errors + s_err
    if isinstance(refs, list) and not refs:
        errors.append("Add at least one source page reference.")
    return {"ok": not errors, "errors": errors, "warnings": result.warnings + s_warn, "block_types": result.block_types}


# ------------------------------------------------------------------ helpers
def _active_chapter(db: Session, chapter_id: uuid.UUID) -> Chapter:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None or chapter.retired_at is not None:
        raise NotFound("Chapter not found.")
    return chapter


def get_item(db: Session, item_id: uuid.UUID, *, for_update: bool = False) -> ContentItem:
    stmt = select(ContentItem).where(ContentItem.id == item_id)
    if for_update:
        stmt = stmt.with_for_update()  # serialise transitions on one item
    item = db.scalar(stmt)
    if item is None:
        raise NotFound("Content item not found.")
    return item


def _working(item: ContentItem) -> ContentVersion:
    if item.working is None:
        raise Conflict("This item has no version in progress.")
    return item.working


def _audit(db: Session, who: Principal, action: str, item: ContentItem, **details: Any) -> None:
    record(
        db,
        actor=who.user.id,
        action=f"content.{action}",
        target_type="content_item",
        target_id=str(item.id),
        details={"state": item.state, "availability": item.availability, **details},
    )


def _expect(item: ContentItem, *states: ItemState) -> None:
    if item.availability == Availability.retired.value:
        raise Conflict("This item has been retired.", state=item.state, availability=item.availability)
    if item.state not in {s.value for s in states}:
        raise Conflict(
            f"This action isn't available while the item is {item.state.replace('_', ' ')}.", state=item.state
        )


def _independent(version: ContentVersion, who: Principal, act: str) -> None:
    if str(who.user.id) in version.contributors:
        raise Forbidden(f"You edited this version, so you can't {act} it. Independent review is required.")


# ------------------------------------------------------------------ operations
def create_item(
    db: Session,
    who: Principal,
    *,
    chapter_id: uuid.UUID | None,
    topic_id: uuid.UUID | None,
    title: str,
    kind: str = "lesson",
    family_of: uuid.UUID | None = None,
    parent_item_id: uuid.UUID | None = None,
) -> ContentItem:
    spec = kinds.get(kind)
    parent: ContentItem | None = None
    if kind == "rubric":
        parent = links.rubric_parent(db, parent_item_id)
        chapter_id, topic_id = parent.chapter_id, parent.topic_id  # a rubric lives with its question
    elif parent_item_id is not None:
        raise Unprocessable("Only rubrics are attached to another item.")
    if chapter_id is None:
        raise Unprocessable("Choose a chapter.")
    chapter = _active_chapter(db, chapter_id)
    book = db.get(BookEdition, chapter.book_id)
    assert book is not None
    subject = db.get(Subject, book.subject_id)
    assert subject is not None
    if not subject.active:
        raise Forbidden("This subject is outside the current academic scope (SCOPE-01).")
    if topic_id is not None:
        topic = db.get(Topic, topic_id)
        if topic is None or topic.chapter_id != chapter.id or topic.retired_at is not None:
            raise Unprocessable("The topic doesn't belong to this chapter.")
    item = ContentItem(
        id=uuid.uuid4(),
        kind=kind,
        chapter_id=chapter.id,
        topic_id=topic_id,
        grade_number=book.grade.number,
        subject_code=subject.code,
        title=title.strip(),
        state=ItemState.draft.value,
        availability=Availability.unpublished.value,
        created_by=who.user.id,
    )
    _require_scoped(db, who, Permission.draft_content, item)
    item.parent_item_id = parent.id if parent else None
    if kind in ("mcq", "written"):
        item.family_id = item.id
        if family_of is not None:
            sibling = db.get(ContentItem, family_of)
            if (
                sibling is None
                or sibling.kind != kind
                or (sibling.grade_number, sibling.subject_code)
                != (
                    item.grade_number,
                    item.subject_code,
                )
            ):
                raise Unprocessable("A variant must belong to a question of the same class and subject.")
            item.family_id = sibling.family_id
    elif family_of is not None:
        raise Unprocessable("Only questions have variant families.")
    version = ContentVersion(
        id=uuid.uuid4(),
        item_id=item.id,
        number=1,
        status=VersionStatus.draft.value,
        revision=1,
        content_schema_version=blocks.CONTENT_SCHEMA_VERSION,
        body=spec.empty_body(),
        block_types=[],
        source_refs=[],
        created_by=who.user.id,
        contributors=[str(who.user.id)],
        updated_by=who.user.id,
    )
    db.add(item)
    db.flush()
    db.add(version)
    db.flush()
    item.working_version_id = version.id
    _audit(
        db,
        who,
        "created",
        item,
        version=1,
        kind=kind,
        chapter_id=str(chapter.id),
        family_id=str(item.family_id) if item.family_id else None,
    )
    db.commit()
    db.refresh(item)
    return item


def save_draft(
    db: Session,
    who: Principal,
    item_id: uuid.UUID,
    *,
    revision: int,
    title: str | None,
    body: object,
    source_refs: object,
) -> ContentItem:
    item = get_item(db, item_id, for_update=True)
    _require_scoped(db, who, Permission.draft_content, item)
    _expect(item, ItemState.draft, ItemState.changes_requested)
    version = _working(item)
    if revision != version.revision:
        editor = db.get(AppUser, version.updated_by)
        raise Conflict(
            "Someone else saved this draft after you opened it. Review their changes before saving again.",
            current={
                "revision": version.revision,
                "title": item.title,
                "body": version.body,
                "source_refs": version.source_refs,
                "updated_at": version.updated_at.isoformat(),
                "updated_by": editor.email if editor else None,
            },
        )
    normalised, errors, types = kinds.get(item.kind).parse_draft(body)
    if normalised is None:
        raise Unprocessable("The content doesn't match the schema.", errors=errors)
    chapter = db.get(Chapter, item.chapter_id)
    assert chapter is not None
    s_err, _, refs = check_sources(db, chapter, source_refs)
    if s_err:
        raise Unprocessable("Some source references are invalid.", errors=s_err)
    version.body = normalised
    version.block_types = types
    version.source_refs = refs
    version.revision += 1
    version.updated_by = who.user.id
    version.updated_at = _now()
    if str(who.user.id) not in version.contributors:
        version.contributors = [*version.contributors, str(who.user.id)]
    if title is not None and title.strip():
        item.title = title.strip()
    if item.state == ItemState.changes_requested.value:
        item.state = ItemState.draft.value
        version.status = VersionStatus.draft.value
    item.updated_at = _now()
    # Autosaves are frequent; the audit trail records state transitions, not each keystroke batch.
    db.commit()
    db.refresh(item)
    return item


def submit(db: Session, who: Principal, item_id: uuid.UUID, note: str | None) -> ContentItem:
    item = get_item(db, item_id, for_update=True)
    _require_scoped(db, who, Permission.draft_content, item)
    _expect(item, ItemState.draft, ItemState.changes_requested)
    version = _working(item)
    if version.number > 1 and not version.change_reason:
        raise Unprocessable("A revision needs a reason before it can be submitted.")
    v = _validate(db, item, version, for_publication=False)
    if not v["ok"]:
        raise Unprocessable("Fix the problems below before submitting.", errors=v["errors"], warnings=v["warnings"])
    version.status = VersionStatus.submitted.value
    version.submitted_at = _now()
    item.state = ItemState.submitted.value
    item.updated_at = _now()
    _audit(db, who, "submitted", item, version=version.number, note=note, warnings=v["warnings"])
    db.commit()
    db.refresh(item)
    return item


def withdraw(db: Session, who: Principal, item_id: uuid.UUID) -> ContentItem:
    item = get_item(db, item_id, for_update=True)
    _require_scoped(db, who, Permission.draft_content, item)
    _expect(item, ItemState.submitted)
    version = _working(item)
    version.status = VersionStatus.draft.value
    item.state = ItemState.draft.value
    item.updated_at = _now()
    _audit(db, who, "withdrawn", item, version=version.number)
    db.commit()
    db.refresh(item)
    return item


def assign_reviewer(db: Session, who: Principal, item_id: uuid.UUID, reviewer_id: uuid.UUID | None) -> ContentItem:
    """Reviewers may claim (assign themselves); publishers may assign anyone eligible or clear the assignment."""
    item = get_item(db, item_id, for_update=True)
    scoped = permissions_for(roles_in_scope(db, who.user.id, item.grade_number, item.subject_code))
    is_publisher = Permission.publish_content in scoped
    if reviewer_id != who.user.id and not is_publisher:
        raise Forbidden("Only a publisher can assign someone else.")
    if reviewer_id is not None:
        if Permission.review_content not in permissions_for(
            roles_in_scope(db, reviewer_id, item.grade_number, item.subject_code)
        ):
            raise Unprocessable("That person isn't a reviewer for this subject and class.")
        if item.working is not None and str(reviewer_id) in item.working.contributors:
            raise Unprocessable("That person edited this version and can't review it.")
    item.assigned_reviewer_id = reviewer_id
    item.updated_at = _now()
    _audit(db, who, "reviewer_assigned", item, reviewer_id=str(reviewer_id) if reviewer_id else None)
    db.commit()
    db.refresh(item)
    return item


def review(
    db: Session,
    who: Principal,
    item_id: uuid.UUID,
    *,
    decision: str,
    comment: str,
    checklist: dict[str, bool] | None = None,
) -> ContentItem:
    item = get_item(db, item_id, for_update=True)
    _require_scoped(db, who, Permission.review_content, item)
    _expect(item, ItemState.submitted)
    version = _working(item)
    _independent(version, who, "approve or review")
    if item.assigned_reviewer_id is not None and item.assigned_reviewer_id != who.user.id:
        raise Forbidden("Another reviewer is assigned to this item.")
    required = kinds.get(item.kind).review_checklist
    checks = {k: bool(v) for k, v in (checklist or {}).items() if k in required}
    if decision == "approve":
        unconfirmed = [k for k in required if not checks.get(k)]
        if unconfirmed:
            raise Unprocessable(
                "Confirm every review check before approving.", errors=[f"Not confirmed: {', '.join(unconfirmed)}."]
            )
        v = _validate(db, item, version, for_publication=False)
        if not v["ok"]:
            raise Unprocessable("This version no longer passes validation.", errors=v["errors"])
        version.status = VersionStatus.approved.value
        version.approved_by = who.user.id
        version.approved_at = _now()
        item.state = ItemState.approved.value
    else:
        version.status = VersionStatus.changes_requested.value
        item.state = ItemState.changes_requested.value
    db.add(
        ReviewDecision(
            version_id=version.id, reviewer_id=who.user.id, decision=decision, comment=comment.strip(), checklist=checks
        )
    )
    item.updated_at = _now()
    _audit(db, who, "approved" if decision == "approve" else "changes_requested", item, version=version.number)
    db.commit()
    db.refresh(item)
    return item


def publish(db: Session, who: Principal, item_id: uuid.UUID) -> ContentItem:
    item = get_item(db, item_id, for_update=True)
    _require_scoped(db, who, Permission.publish_content, item)
    _expect(item, ItemState.approved)
    version = _working(item)
    _independent(version, who, "publish")
    v = _validate(db, item, version, for_publication=True)
    if not v["ok"]:
        raise Unprocessable("This version can't be published yet.", errors=v["errors"], warnings=v["warnings"])
    previous = item.published
    if previous is not None and previous.id != version.id:
        previous.status = VersionStatus.superseded.value
        db.flush()  # free the one-published-version index before marking the new one
    version.status = VersionStatus.published.value
    version.published_by = who.user.id
    version.published_at = _now()
    resolved = item.availability == Availability.quarantined.value
    item.published_version_id = version.id
    item.state = ItemState.published.value
    item.availability = Availability.live.value
    item.availability_reason = None
    item.quarantine_level = None
    item.updated_at = _now()
    _audit(
        db,
        who,
        "published",
        item,
        version=version.number,
        resolved_quarantine=resolved,
        superseded=previous.number if previous is not None and previous.id != version.id else None,
    )
    db.commit()
    db.refresh(item)
    return item


def previous_published(db: Session, item: ContentItem) -> ContentVersion | None:
    """The most recent earlier version that was once published (a rollback target)."""
    current = item.published
    if current is None:
        return None
    return db.scalar(
        select(ContentVersion)
        .where(
            ContentVersion.item_id == item.id,
            ContentVersion.status == VersionStatus.superseded.value,
            ContentVersion.published_at.is_not(None),
            ContentVersion.number < current.number,
        )
        .order_by(ContentVersion.number.desc())
        .limit(1)
    )


def rollback(db: Session, who: Principal, item_id: uuid.UUID, reason: str) -> ContentItem:
    """Put the previously published version back in front of learners (P06.S3.T3). Nothing is erased: the rolled-back
    version stays in the history as superseded, both moves are audited, attempts keep their pinned versions, and the
    restored version must still pass today's publication gate (rights, renderer, links)."""
    from portal_api.modules.assessment.models import McqAdjudication

    item = get_item(db, item_id, for_update=True)
    _require_scoped(db, who, Permission.publish_content, item)
    if item.availability == Availability.retired.value:
        raise Conflict("Retired content can't be rolled back.")
    current = item.published
    target = previous_published(db, item)
    if current is None or target is None:
        raise Conflict("There is no earlier published version to roll back to.")
    if db.scalar(
        select(McqAdjudication.id).where(McqAdjudication.version_id == target.id, McqAdjudication.status == "effective")
    ):
        raise Conflict("The earlier version has a recorded score correction; it can't go back to learners.")
    v = _validate(db, item, target, for_publication=True)
    if not v["ok"]:
        raise Unprocessable("The earlier version can't be published today.", errors=v["errors"], warnings=v["warnings"])
    current.status = VersionStatus.superseded.value
    db.flush()  # free the one-published-version index
    target.status = VersionStatus.published.value
    if item.working_version_id == current.id:
        item.working_version_id = target.id  # no revision in progress: the restored version is the working one
    item.published_version_id = target.id
    resolved = item.availability == Availability.quarantined.value
    item.availability = Availability.live.value
    item.availability_reason = None
    item.quarantine_level = None
    item.updated_at = _now()
    _audit(
        db,
        who,
        "rolled_back",
        item,
        reason=reason.strip(),
        from_version=current.number,
        to_version=target.number,
        resolved_quarantine=resolved,
    )
    db.commit()
    db.refresh(item)
    return item


def revise(db: Session, who: Principal, item_id: uuid.UUID, reason: str) -> ContentItem:
    """Start a new version of published content. Learners keep seeing the published version until the new one is
    approved and published (P06.S3.T3)."""
    item = get_item(db, item_id, for_update=True)
    _require_scoped(db, who, Permission.draft_content, item)
    _expect(item, ItemState.published)
    base = item.published
    assert base is not None
    number = max(v.number for v in item.versions) + 1
    version = ContentVersion(
        id=uuid.uuid4(),
        item_id=item.id,
        number=number,
        status=VersionStatus.draft.value,
        revision=1,
        content_schema_version=blocks.CONTENT_SCHEMA_VERSION,
        body=base.body,
        block_types=base.block_types,
        source_refs=base.source_refs,
        change_reason=reason.strip(),
        created_by=who.user.id,
        contributors=[str(who.user.id)],
        updated_by=who.user.id,
    )
    db.add(version)
    db.flush()
    item.working_version_id = version.id
    item.state = ItemState.draft.value
    item.assigned_reviewer_id = None
    item.updated_at = _now()
    _audit(db, who, "revision_started", item, version=number, reason=reason.strip(), from_version=base.number)
    db.commit()
    db.refresh(item)
    return item


def quarantine(db: Session, who: Principal, item_id: uuid.UUID, reason: str, level: str | None = None) -> ContentItem:
    """Hide live content from learners while a suspected defect is investigated (§5.7). Editorial work on a corrected
    version continues independently."""
    item = get_item(db, item_id, for_update=True)
    _require_scoped(db, who, Permission.quarantine_content, item)
    levels = kinds.get(item.kind).quarantine_levels
    if item.availability == Availability.quarantined.value and levels and level in levels:
        # A suspected defect confirmed (or re-classified) after review: change the level, never via release.
        if level == item.quarantine_level:
            raise Conflict("The question is already quarantined at that level.")
        if level == "SOFT":
            _no_effective_correction(db, item)  # a recorded correction is a confirmed defect, not a suspicion
        previous = item.quarantine_level
        item.quarantine_level = level
        item.availability_reason = reason.strip()
        item.updated_at = _now()
        _audit(db, who, "quarantine_level_changed", item, reason=reason.strip(), level=level, previous=previous)
        db.commit()
        db.refresh(item)
        return item
    if item.availability != Availability.live.value:
        raise Conflict("Only live content can be quarantined.", availability=item.availability)
    if levels and level not in levels:
        raise Unprocessable(f"Choose a quarantine level: {', '.join(levels)}.")
    if not levels and level is not None:
        raise Unprocessable("This kind of content has no quarantine levels.")
    item.quarantine_level = level
    item.availability = Availability.quarantined.value
    item.availability_reason = reason.strip()
    item.updated_at = _now()
    _audit(db, who, "quarantined", item, reason=reason.strip(), level=level)
    db.commit()
    db.refresh(item)
    return item


def set_access_tier(db: Session, who: Principal, item_id: uuid.UUID, tier: str, reason: str) -> ContentItem:
    """Mark a lesson as a free preview or premium (R07). Publishers in scope, with MFA (the permission is MFA-gated);
    every change is audited with its reason. Questions and rubrics are never readable through lessons at any tier."""
    item = get_item(db, item_id, for_update=True)
    _require_scoped(db, who, Permission.publish_content, item)
    if not kinds.get(item.kind).learner_readable:
        raise Unprocessable("Only lessons have a reading tier; questions are never shown as lessons.")
    if tier not in ("preview", "premium"):
        raise Unprocessable("Choose preview or premium.")
    if item.access_tier == tier:
        return item
    previous = item.access_tier
    item.access_tier = tier
    item.updated_at = _now()
    _audit(db, who, "access_tier_changed", item, reason=reason.strip(), previous=previous, tier=tier)
    db.commit()
    db.refresh(item)
    return item


def set_question_pool(db: Session, who: Principal, item_id: uuid.UUID, pool: str, reason: str) -> ContentItem:
    """P08.S3.T3: reserve a question for mocks (never in practice tests) or return it to practice. Publishers in
    scope (MFA); audited with a reason. Forms already built keep their questions."""
    item = get_item(db, item_id, for_update=True)
    _require_scoped(db, who, Permission.publish_content, item)
    if item.kind != "mcq":
        raise Unprocessable("Only multiple-choice questions belong to a question pool.")
    if pool not in ("practice", "mock"):
        raise Unprocessable("Choose practice or mock.")
    if item.question_pool == pool:
        return item
    previous = item.question_pool
    item.question_pool = pool
    item.updated_at = _now()
    _audit(db, who, "question_pool_changed", item, reason=reason.strip(), previous=previous, pool=pool)
    db.commit()
    db.refresh(item)
    return item


def _no_effective_correction(db: Session, item: ContentItem) -> None:
    """A confirmed defect with a recorded score correction stays quarantined: publish a corrected version instead."""
    from portal_api.modules.assessment.models import McqAdjudication

    if item.published_version_id and db.scalar(
        select(McqAdjudication.id).where(
            McqAdjudication.version_id == item.published_version_id, McqAdjudication.status == "effective"
        )
    ):
        raise Conflict("A score correction is recorded for this version; publish a corrected version instead.")


def release(db: Session, who: Principal, item_id: uuid.UUID, reason: str) -> ContentItem:
    """Return quarantined content to learners unchanged (the suspected defect was not confirmed)."""
    item = get_item(db, item_id, for_update=True)
    _require_scoped(db, who, Permission.quarantine_content, item)
    if item.availability != Availability.quarantined.value:
        raise Conflict("Only quarantined content can be released.", availability=item.availability)
    _no_effective_correction(db, item)
    released_level = item.quarantine_level
    item.availability = Availability.live.value
    item.availability_reason = None
    item.quarantine_level = None
    item.updated_at = _now()
    _audit(db, who, "released", item, reason=reason.strip(), level=released_level)
    db.commit()
    db.refresh(item)
    return item


def retire(db: Session, who: Principal, item_id: uuid.UUID, reason: str) -> ContentItem:
    item = get_item(db, item_id, for_update=True)
    _require_scoped(db, who, Permission.publish_content, item)
    if item.availability == Availability.retired.value:
        raise Conflict("This item is already retired.")
    working = item.working
    if working is not None and working.status not in (VersionStatus.published.value, VersionStatus.superseded.value):
        working.status = VersionStatus.superseded.value
    prior = item.availability
    item.availability = Availability.retired.value
    item.availability_reason = reason.strip()
    item.updated_at = _now()
    _audit(db, who, "retired", item, reason=reason.strip(), prior_availability=prior)
    db.commit()
    db.refresh(item)
    return item


def set_publication_rights(
    db: Session, who: Principal, source_id: uuid.UUID, *, rights: str, evidence: str
) -> SourceDocument:
    doc = db.get(SourceDocument, source_id)
    if doc is None:
        raise NotFound("Source document not found.")
    prior = doc.publication_rights
    doc.publication_rights = rights
    doc.publication_rights_evidence = evidence.strip()
    doc.publication_rights_set_by = who.user.id
    doc.publication_rights_set_at = _now()
    record(
        db,
        actor=who.user.id,
        action="source.publication_rights_set",
        target_type="source_document",
        target_id=str(doc.id),
        details={"source_id": doc.source_id, "from": prior, "to": rights, "evidence": evidence.strip()},
    )
    db.commit()
    return doc
