"""Cross-item rules that need the database (rubric ↔ written question). Kind validators stay pure; these run inside
the workflow's submission and publication validation."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.modules.content import written
from portal_api.modules.content.models import Availability, ContentItem, ContentVersion, VersionStatus


def check(db: Session, item: ContentItem, version: ContentVersion, *, for_publication: bool) -> list[str]:
    if item.kind == "rubric":
        return _rubric(db, item, version, for_publication=for_publication)
    if item.kind == "written" and for_publication:
        return _written_has_rubric(db, item, version)
    if item.kind == "storyboard":
        from portal_api.modules.content import storyboard

        return storyboard.claim_errors(version.body, version.source_refs)
    return []


def _rubric(db: Session, item: ContentItem, version: ContentVersion, *, for_publication: bool) -> list[str]:
    r, errs = written.parse_rubric(version.body)
    if r is None or r.question_version_id is None:
        return errs
    parent = db.get(ContentItem, item.parent_item_id) if item.parent_item_id else None
    if parent is None or parent.kind != "written":
        return ["This rubric isn't attached to a written question."]
    qv = db.get(ContentVersion, r.question_version_id)
    if qv is None or qv.item_id != parent.id:
        return ["The rubric must mark a version of its own question."]
    q, q_errs = written.parse_written(qv.body)
    if q is None:
        return ["The question version can't be read: " + "; ".join(q_errs)]
    errors = written.reconcile(r, q)
    if for_publication and qv.status not in (VersionStatus.approved.value, VersionStatus.published.value):
        errors.append(f"Question version {qv.number} must be academically approved before its rubric is published.")
    return errors


def _written_has_rubric(db: Session, item: ContentItem, version: ContentVersion) -> list[str]:
    rubrics = db.execute(
        select(ContentItem, ContentVersion)
        .join(ContentVersion, ContentVersion.id == ContentItem.published_version_id)
        .where(
            ContentItem.kind == "rubric",
            ContentItem.parent_item_id == item.id,
            ContentItem.availability == Availability.live.value,
        )
    ).all()
    for _, rv in rubrics:
        if str(rv.body.get("question_version_id")) == str(version.id):
            return []
    return [f"Publish a reviewed rubric for question version {version.number} before publishing the question."]


def rubric_parent(db: Session, parent_item_id: uuid.UUID | None) -> ContentItem:
    from portal_api.errors import Unprocessable

    parent = db.get(ContentItem, parent_item_id) if parent_item_id else None
    if parent is None or parent.kind != "written":
        raise Unprocessable("A rubric must be attached to a written question.")
    return parent
