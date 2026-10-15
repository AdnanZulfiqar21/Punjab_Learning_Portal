"""Portable content export (roadmap P06.S4.T2; EXPORT-01). Format documented in `docs/content-import.md`.

One class and subject per file: the book and its chapter/topic structure (stable keys), every item in that scope with
its state, availability and all versions (body, source references, status, publication time), and any MCQ score
corrections. Publishers in scope with MFA only; every export is audited with its size. Learner data, attempts and
staff notes are never included.

Schema version 2 (P06.S4.T2, EXPORT-02) adds the mappings and media references:

* `concepts`: the subject's concepts mapped to this book's topics, each with its topic keys in this book only (Class XI
  and XII are never mixed), its prerequisites by concept code (and bridging lesson) and its syllabus inclusion records;
* `assets`: every archived asset version an exported version's body names (diagrams, handouts, fallback images), with
  its kind, checksum, size, media type, delivery state and provenance. Files themselves are not in the document.
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
SCHEMA_VERSION = 2


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
    concepts = _concepts(db, subject_code, topics)
    assets = _assets(db, [v["body"] for it in out_items for v in it["versions"]])
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
        "concepts": concepts,
        "assets": assets,
    }
    body = json.dumps(doc_out, ensure_ascii=False, indent=1).encode("utf-8")
    record(
        db,
        actor=who.user.id,
        action="content.exported",
        target_type="book_edition",
        target_id=str(book.id),
        details={
            "grade": grade,
            "subject": subject_code,
            "items": len(out_items),
            "concepts": len(concepts),
            "assets": len(assets),
            "bytes": len(body),
        },
    )
    db.commit()
    return body, f"content-{grade}-{subject_code}-{datetime.now(UTC):%Y%m%d}.json"


def _concepts(db: Session, subject_code: str, topics: list[Topic]) -> list[dict[str, Any]]:
    """EXPORT-02: the subject's concepts mapped to this book's topics, with prerequisites and inclusion records."""
    from portal_api.modules.content.concepts import Concept, ConceptPrerequisite, ConceptTopic
    from portal_api.modules.content.inclusion import InclusionRecord

    keys = {t.id: t.natural_key for t in topics}
    if not keys:
        return []
    links = db.execute(
        select(ConceptTopic.concept_id, ConceptTopic.topic_id).where(ConceptTopic.topic_id.in_(list(keys)))
    ).all()
    mapped: dict[Any, list[str]] = {}
    for concept_id, topic_id in links:
        mapped.setdefault(concept_id, []).append(keys[topic_id])
    concepts = list(
        db.scalars(
            select(Concept)
            .where(Concept.id.in_(list(mapped)), Concept.subject_code == subject_code)
            .order_by(Concept.code)
        )
    )
    codes = dict(db.execute(select(Concept.id, Concept.code).where(Concept.subject_code == subject_code)).all())
    out = []
    for c in concepts:
        requires = db.execute(
            select(ConceptPrerequisite.requires_id, ConceptPrerequisite.bridging_lesson_id).where(
                ConceptPrerequisite.concept_id == c.id
            )
        ).all()
        records = db.scalars(
            select(InclusionRecord)
            .where(InclusionRecord.concept_id == c.id)
            .order_by(InclusionRecord.scope, InclusionRecord.year)
        )
        out.append(
            {
                "code": c.code,
                "title": c.title,
                "statement": c.statement,
                "status": c.status,
                "published_at": c.published_at.isoformat() if c.published_at else None,
                "source_refs": c.source_refs,
                "topics": sorted(mapped[c.id]),
                "requires": sorted(
                    (
                        {"code": codes.get(r), "bridging_lesson_id": str(b) if b else None}
                        for r, b in requires
                        if codes.get(r)
                    ),
                    key=lambda x: str(x["code"]),
                ),
                "inclusion": [
                    {
                        "scope": r.scope,
                        "year": r.year,
                        "state": r.state,
                        "reason": r.reason,
                        "source": r.source,
                        "source_version": r.source_version,
                        "status": r.status,
                        "published_at": r.published_at.isoformat() if r.published_at else None,
                    }
                    for r in records
                ],
            }
        )
    return out


def _assets(db: Session, bodies: list[Any]) -> list[dict[str, Any]]:
    """EXPORT-02: every archived asset version the exported bodies name, as a reference (never the file)."""
    from portal_api.modules.content.assets import Asset, block_refs, resolve

    ids = sorted({vid for body in bodies for _, vid, _ in block_refs(body)})
    out = []
    for vid in ids:
        v = resolve(db, vid)
        a = db.get(Asset, v.asset_id) if v is not None else None
        if v is None or a is None:
            out.append({"asset_version_id": vid, "missing": True})
            continue
        out.append(
            {
                "asset_version_id": vid,
                "asset_id": str(a.id),
                "external_id": a.external_ref,
                "kind": a.kind,
                "title": a.title,
                "version": v.number,
                "media_type": v.media_type,
                "sha256": v.master_sha256,
                "bytes": v.master_bytes,
                "width": v.width,
                "height": v.height,
                "pages": v.pages,
                "delivery_state": v.delivery_state,
                "provenance": {
                    k: v.provenance[k] for k in ("source", "author", "licence", "tool") if k in v.provenance
                },
                "missing": False,
            }
        )
    return out
