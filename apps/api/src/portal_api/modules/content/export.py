"""Portable content export (roadmap P06.S4.T2; EXPORT-01). Format documented in `docs/content-import.md`.

One class and subject per file: the book and its chapter/topic structure (stable keys), every item in that scope with
its state, availability and all versions (body, source references, status, publication time), and any MCQ score
corrections. Publishers in scope with MFA only; every export is audited with its size. Learner data, attempts and
staff notes are never included.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.errors import Forbidden, NotFound
from portal_api.modules.audit.models import record
from portal_api.modules.content import workflow
from portal_api.modules.content.models import ContentItem, ContentVersion
from portal_api.modules.curriculum.models import BookEdition, Chapter, Grade, SourceDocument, Subject, Topic
from portal_api.modules.identity.deps import Principal
from portal_api.modules.identity.permissions import Permission, permissions_for

FORMAT = "portal-content-export"
SCHEMA_VERSION = 1


def export(db: Session, who: Principal, grade: int, subject_code: str) -> tuple[bytes, str]:
    from portal_api.modules.assessment.models import McqAdjudication

    if Permission.publish_content not in permissions_for(workflow.roles_in_scope(db, who.user.id, grade, subject_code)):
        raise Forbidden("You can only export the classes and subjects you publish.")
    book = db.scalar(
        select(BookEdition)
        .join(Grade, Grade.id == BookEdition.grade_id)
        .join(Subject, Subject.id == BookEdition.subject_id)
        .where(Grade.number == grade, Subject.code == subject_code)
    )
    if book is None:
        raise NotFound("No book for that class and subject.")
    doc = db.get(SourceDocument, book.source_document_id) if book.source_document_id else None
    chapters = list(db.scalars(select(Chapter).where(Chapter.book_id == book.id).order_by(Chapter.display_order)))
    by_chapter = {c.id: c for c in chapters}
    topics = (
        list(
            db.scalars(
                select(Topic).where(Topic.chapter_id.in_([c.id for c in chapters])).order_by(Topic.display_order)
            )
        )
        if chapters
        else []
    )
    topic_key = {t.id: t.natural_key for t in topics}
    items = (
        list(
            db.scalars(
                select(ContentItem)
                .where(ContentItem.chapter_id.in_([c.id for c in chapters]))
                .order_by(ContentItem.created_at, ContentItem.id)
            )
        )
        if chapters
        else []
    )
    out_items: list[dict[str, Any]] = []
    for it in items:
        versions = list(
            db.scalars(select(ContentVersion).where(ContentVersion.item_id == it.id).order_by(ContentVersion.number))
        )
        corrections = list(
            db.scalars(
                select(McqAdjudication).where(McqAdjudication.item_id == it.id).order_by(McqAdjudication.decided_at)
            )
        )
        out_items.append(
            {
                "id": str(it.id),
                "external_id": it.external_ref,
                "kind": it.kind,
                "chapter": by_chapter[it.chapter_id].natural_key,
                "topic": topic_key.get(it.topic_id) if it.topic_id else None,
                "parent_id": str(it.parent_item_id) if it.parent_item_id else None,
                "family_id": str(it.family_id) if it.family_id else None,
                "title": it.title,
                "state": it.state,
                "availability": it.availability,
                "quarantine_level": it.quarantine_level,
                "access_tier": it.access_tier,
                "published_version": next((v.number for v in versions if v.id == it.published_version_id), None),
                "versions": [
                    {
                        "number": v.number,
                        "status": v.status,
                        "content_schema_version": v.content_schema_version,
                        "body": v.body,
                        "source_refs": v.source_refs,
                        "published_at": v.published_at.isoformat() if v.published_at else None,
                    }
                    for v in versions
                ],
                "score_corrections": [
                    {
                        "version": next((v.number for v in versions if v.id == c.version_id), None),
                        "defect": c.defect,
                        "corrected_option_id": c.corrected_option_id,
                        "reason": c.reason,
                        "status": c.status,
                        "decided_at": c.decided_at.isoformat(),
                    }
                    for c in corrections
                ],
            }
        )
    doc_out = {
        "format": FORMAT,
        "schema_version": SCHEMA_VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
        "grade": grade,
        "subject": subject_code,
        "book": {
            "title": book.title,
            "source_id": doc.source_id if doc else None,
            "source_document_id": str(doc.id) if doc else None,
            "publication_rights": doc.publication_rights if doc else None,
        },
        "chapters": [
            {
                "key": c.natural_key,
                "id": str(c.id),
                "number": c.number,
                "title": c.title,
                "retired": c.retired_at is not None,
                "topics": [
                    {"key": t.natural_key, "number": t.number, "title": t.title, "retired": t.retired_at is not None}
                    for t in topics
                    if t.chapter_id == c.id
                ],
            }
            for c in chapters
        ],
        "items": out_items,
    }
    body = json.dumps(doc_out, ensure_ascii=False, indent=1).encode("utf-8")
    record(
        db,
        actor=who.user.id,
        action="content.exported",
        target_type="book_edition",
        target_id=str(book.id),
        details={"grade": grade, "subject": subject_code, "items": len(out_items), "bytes": len(body)},
    )
    db.commit()
    return body, f"content-{grade}-{subject_code}-{datetime.now(UTC):%Y%m%d}.json"
