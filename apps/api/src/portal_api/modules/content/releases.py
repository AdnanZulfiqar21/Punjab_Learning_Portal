"""Content releases (P06.S3.T2, RELEASE-01): publish several approved items together, or none of them.

Every item must be approved, in the publisher's scope and not edited by the publisher. The items are put live in one
transaction and then each is checked against today's publication gate (renderer floor, rights, links) in the state the
release leaves behind, so a rubric and its written question, or a passage and its questions, can go out together. If
any check fails nothing is published and every problem is reported. A release is rolled back the same way: each item
goes back to the version it had before (a restored version passes today's gate too), or off learners' screens if the
release first published it. Nothing is deleted; attempts keep their pinned versions.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.errors import Conflict, Forbidden, NotFound, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.content import workflow
from portal_api.modules.content.models import (
    Availability,
    ContentItem,
    ContentRelease,
    ContentReleaseEntry,
    ContentVersion,
    ItemState,
    VersionStatus,
)
from portal_api.modules.identity.deps import Principal
from portal_api.modules.identity.permissions import Permission, permissions_for

MAX_ITEMS = 100


def _now() -> datetime:
    return datetime.now(UTC)


def _lock(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, ContentItem]:
    """Lock the items in one fixed order (by id) so two releases sharing items can't deadlock."""
    items = {}
    for item_id in sorted(set(ids)):
        try:
            items[item_id] = workflow.get_item(db, item_id, for_update=True)
        except NotFound:
            raise NotFound(f"Content item {item_id} doesn't exist.") from None
    return items


def _refuse(
    db: Session, message: str, problems: dict[uuid.UUID, list[str]], items: dict[uuid.UUID, ContentItem]
) -> None:
    db.rollback()
    raise Unprocessable(
        message,
        items=[
            {"item_id": str(i), "title": items[i].title if i in items else "", "errors": errs}
            for i, errs in problems.items()
        ],
    )


def _in_scope(db: Session, who: Principal, item: ContentItem) -> bool:
    roles = workflow.roles_in_scope(db, who.user.id, item.grade_number, item.subject_code)
    return Permission.publish_content in permissions_for(roles)


def publish(db: Session, who: Principal, item_ids: list[uuid.UUID], label: str, reason: str) -> ContentRelease:
    ids = list(dict.fromkeys(item_ids))
    if not 1 <= len(ids) <= MAX_ITEMS:
        raise Unprocessable(f"A release publishes between 1 and {MAX_ITEMS} items.")
    items = _lock(db, ids)
    problems: dict[uuid.UUID, list[str]] = {}
    for item_id in ids:
        item = items[item_id]
        if not _in_scope(db, who, item):
            problems[item_id] = ["This item is outside the subjects and classes your role covers."]
        elif item.availability == Availability.retired.value:
            problems[item_id] = ["This item has been retired."]
        elif item.state != ItemState.approved.value or item.working is None:
            problems[item_id] = [f"Only approved items can be published; this one is {item.state.replace('_', ' ')}."]
        else:
            try:
                workflow._independent(item.working, who, "publish")
            except Forbidden as e:
                problems[item_id] = [str(e.detail)]
    if problems:
        _refuse(db, "Nothing was published.", problems, items)

    now = _now()
    release = ContentRelease(
        label=label.strip(), reason=reason.strip(), status="published", published_by=who.user.id, published_at=now
    )
    db.add(release)
    db.flush()
    versions: dict[uuid.UUID, ContentVersion] = {}
    for position, item_id in enumerate(ids):
        item = items[item_id]
        version = item.working
        assert version is not None
        versions[item_id] = version
        previous = workflow.put_live(db, who, item, version, release_id=str(release.id))
        db.add(
            ContentReleaseEntry(
                release_id=release.id,
                item_id=item.id,
                version_id=version.id,
                previous_version_id=previous.id if previous is not None else None,
                position=position,
            )
        )
    db.flush()
    for item_id in ids:  # today's gate, in the state the whole release leaves behind
        v = workflow.validate_version(db, items[item_id], versions[item_id], for_publication=True)
        if not v["ok"]:
            problems[item_id] = v["errors"]
    if problems:
        _refuse(db, "Nothing was published: some items don't pass the publication checks yet.", problems, items)
    record(
        db,
        actor=who.user.id,
        action="content.release_published",
        target_type="content_release",
        target_id=str(release.id),
        details={"label": release.label, "reason": release.reason, "items": [str(i) for i in ids]},
    )
    db.commit()
    db.refresh(release)
    return release


def rollback(db: Session, who: Principal, release_id: uuid.UUID, reason: str) -> ContentRelease:
    from portal_api.modules.assessment.models import McqAdjudication

    release = db.get(ContentRelease, release_id, with_for_update=True)
    if release is None or not visible(db, who, release):
        raise NotFound("Release not found.")
    if release.status != "published":
        raise Conflict("This release has already been rolled back.")
    entries = list(release.entries)
    items = _lock(db, [e.item_id for e in entries])
    problems: dict[uuid.UUID, list[str]] = {}
    for e in entries:
        item = items[e.item_id]
        if not _in_scope(db, who, item):
            problems[e.item_id] = ["This item is outside the subjects and classes your role covers."]
        elif item.availability == Availability.retired.value:
            problems[e.item_id] = ["This item has been retired since the release."]
        elif item.published_version_id != e.version_id:
            problems[e.item_id] = [
                "A newer version has been published since this release; roll that item back on its own."
            ]
        elif e.previous_version_id is not None and db.scalar(
            select(McqAdjudication.id).where(
                McqAdjudication.version_id == e.previous_version_id, McqAdjudication.status == "effective"
            )
        ):
            problems[e.item_id] = ["The earlier version has a recorded score correction; it can't go back to learners."]
    if problems:
        _refuse(db, "Nothing was rolled back.", problems, items)

    restored: list[tuple[ContentItem, ContentVersion]] = []
    for e in reversed(entries):
        item = items[e.item_id]
        current = db.get(ContentVersion, e.version_id)
        assert current is not None
        if e.previous_version_id is None:  # first published by this release: take it off learners' screens
            current.status = VersionStatus.approved.value
            item.published_version_id = None
            item.availability = Availability.unpublished.value
            item.availability_reason = None
            item.quarantine_level = None
            if item.working_version_id == current.id:
                item.state = ItemState.approved.value
            item.updated_at = _now()
            workflow._audit(
                db,
                who,
                "release_withdrawn",
                item,
                version=current.number,
                release_id=str(release.id),
                reason=reason.strip(),
            )
            continue
        target = db.get(ContentVersion, e.previous_version_id)
        assert target is not None
        current.status = VersionStatus.superseded.value
        db.flush()  # free the one-published-version index
        target.status = VersionStatus.published.value
        if item.working_version_id == current.id:
            item.working_version_id = target.id
        item.published_version_id = target.id
        item.availability = Availability.live.value
        item.availability_reason = None
        item.quarantine_level = None
        item.updated_at = _now()
        workflow._audit(
            db,
            who,
            "rolled_back",
            item,
            reason=reason.strip(),
            from_version=current.number,
            to_version=target.number,
            release_id=str(release.id),
        )
        restored.append((item, target))
    db.flush()
    for item, target in restored:  # a restored version must still pass today's gate
        v = workflow.validate_version(db, item, target, for_publication=True)
        if not v["ok"]:
            problems[item.id] = v["errors"]
    if problems:
        _refuse(db, "Nothing was rolled back: some earlier versions can't be published today.", problems, items)
    release.status = "rolled_back"
    release.rolled_back_by = who.user.id
    release.rolled_back_at = _now()
    release.rollback_reason = reason.strip()
    record(
        db,
        actor=who.user.id,
        action="content.release_rolled_back",
        target_type="content_release",
        target_id=str(release.id),
        details={"reason": release.rollback_reason, "items": [str(e.item_id) for e in entries]},
    )
    db.commit()
    db.refresh(release)
    return release


def visible(db: Session, who: Principal, release: ContentRelease) -> bool:
    """A publisher sees a release only if every item in it is within their publishing scope."""
    for e in release.entries:
        item = db.get(ContentItem, e.item_id)
        if item is None or not _in_scope(db, who, item):
            return False
    return True


def listing(db: Session, who: Principal, limit: int = 50) -> list[ContentRelease]:
    recent = db.scalars(select(ContentRelease).order_by(ContentRelease.published_at.desc()).limit(limit * 4)).all()
    return [r for r in recent if visible(db, who, r)][:limit]


def entry_rows(db: Session, release: ContentRelease) -> list[dict[str, Any]]:
    rows = []
    for e in release.entries:
        item = db.get(ContentItem, e.item_id)
        version = db.get(ContentVersion, e.version_id)
        previous = db.get(ContentVersion, e.previous_version_id) if e.previous_version_id else None
        assert item is not None and version is not None
        rows.append(
            {
                "item_id": item.id,
                "title": item.title,
                "kind": item.kind,
                "version": version.number,
                "previous_version": previous.number if previous is not None else None,
                "current_version": item.published.number if item.published is not None else None,
                "availability": item.availability,
            }
        )
    return rows
