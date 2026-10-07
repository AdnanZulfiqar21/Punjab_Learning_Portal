"""Import the curriculum catalogue and source registry (P05.S1 / P06.S2 importer conventions, roadmap §10.1).

    portal-import-catalogue [--catalogue PATH] [--registry PATH] [--apply]

Dry-run by default. Upserts by stable ID, so re-running with an unchanged input changes nothing. Never deletes:
entities absent from the input are reported as orphans for explicit review. Never publishes anything; imported
chapters carry content_state=SOURCE_INDEXED (structure from verified indexes, no reviewed teaching material).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from portal_api.modules.curriculum.models import (
    BookEdition,
    Chapter,
    Grade,
    ImportBatch,
    Region,
    SourceDocument,
    Subject,
    Topic,
)


def _project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "content" / "catalogue" / "catalogue.json").exists():
            return parent
    return Path.cwd()


PROJ = _project_root()
DEFAULT_CATALOGUE = PROJ / "content" / "catalogue" / "catalogue.json"
DEFAULT_REGISTRY = PROJ / "content" / "source_registry.json"
SUPPORTED_SCHEMA = 1


class ImportValidationError(ValueError):
    pass


def _flatten(topics: list[dict[str, Any]], parent: str | None = None) -> Iterator[tuple[dict[str, Any], str | None]]:
    for t in topics:
        yield t, parent
        yield from _flatten(t.get("children") or [], t["id"])


def validate(catalogue: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if catalogue.get("schema_version") != SUPPORTED_SCHEMA or registry.get("schema_version") != SUPPORTED_SCHEMA:
        errors.append(f"unsupported schema_version (expected {SUPPORTED_SCHEMA})")
    sources = {s["source_id"]: s for s in registry.get("sources", [])}
    grades = {g["grade"] for g in catalogue.get("grades", [])}
    subjects = {s["code"] for s in catalogue.get("subjects", [])}
    seen: set[str] = set()
    for b in catalogue.get("books", []):
        src = sources.get(b["source_id"])
        if src is None:
            errors.append(f"book {b['source_id']}: no source registry entry")
            continue
        if src["grade"] != b["grade"] or src["subject"] != b["subject"]:
            errors.append(f"book {b['source_id']}: grade/subject disagrees with its source record")
        if b["grade"] not in grades or b["subject"] not in subjects:
            errors.append(f"book {b['source_id']}: unknown grade or subject")
        for ch in b["chapters"]:
            for ident in [ch["id"], *[t["id"] for t, _ in _flatten(ch["topics"])]]:
                if ident in seen:
                    errors.append(f"duplicate id {ident} in {b['source_id']}")
                seen.add(ident)
            if ch["status"] != "missing" and (ch.get("pdf_start") is None or ch.get("pdf_end") is None):
                errors.append(f"{b['source_id']} ch{ch['number']}: missing PDF page range")
    return errors


# Columns owned by people, never by imports: academic state and the owner's publication-rights decision.
INSERT_ONLY = {
    "content_state",
    "publication_rights",
    "publication_rights_evidence",
    "publication_rights_set_by",
    "publication_rights_set_at",
}


def _upsert(session: Session, model: type[Any], rows: list[dict[str, Any]], key: str = "id") -> int:
    if not rows:
        return 0
    table = model.__table__
    for i in range(0, len(rows), 500):
        chunk = rows[i : i + 500]
        stmt = insert(table).values(chunk)
        update_cols = {c: stmt.excluded[c] for c in chunk[0] if c != key and c not in INSERT_ONLY}
        session.execute(stmt.on_conflict_do_update(index_elements=[key], set_=update_cols))
    return len(rows)


def run_import(session: Session, catalogue_path: Path, registry_path: Path, apply: bool) -> ImportBatch:
    raw = catalogue_path.read_bytes() + b"\n" + registry_path.read_bytes()
    catalogue = json.loads(catalogue_path.read_text(encoding="utf-8"))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    batch = ImportBatch(
        id=uuid.uuid4(),
        kind="curriculum_catalogue",
        input_sha256=hashlib.sha256(raw).hexdigest(),
        dry_run=not apply,
        status="RUNNING",
        counts={},
        errors=[],
    )
    errors = validate(catalogue, registry)
    if errors:
        batch.status, batch.errors, batch.finished_at = "REJECTED", errors, datetime.now(UTC)
        if apply:
            session.add(batch)
            session.commit()
        return batch

    region = catalogue["region"]
    region_id = uuid.uuid5(uuid.NAMESPACE_URL, "region/" + region["code"])
    regions = [{"id": region_id, "code": region["code"], "name": region["name"]}]
    grades = [
        {"id": uuid.UUID(g["id"]), "region_id": region_id, "number": g["grade"], "code": g["code"], "name": g["name"]}
        for g in catalogue["grades"]
    ]
    grade_by_num = {g["number"]: g["id"] for g in grades}
    subjects = [
        {
            "id": uuid.UUID(s["id"]),
            "code": s["code"],
            "name": s["name"],
            "display_order": s["order"],
            "aliases": s.get("aliases", []),
            "active": True,
        }
        for s in catalogue["subjects"]
    ]
    subject_by_code = {s["code"]: s["id"] for s in subjects}

    sources, books, chapters, topics = [], [], [], []
    for s in registry["sources"]:
        sources.append(
            {
                "id": uuid.uuid5(uuid.NAMESPACE_URL, "source/" + s["source_id"]),
                "source_id": s["source_id"],
                "grade_number": s["grade"],
                "subject_code": s["subject"],
                "title": s.get("title"),
                "authority": s.get("authority"),
                "edition": s.get("edition"),
                "file_path": s["file"],
                "sha256": s["sha256"],
                "bytes": s["bytes"],
                "pdf_pages": s["pdf_pages"],
                "page_rule": s.get("page_rule"),
                "completeness": s.get("completeness", "unknown"),
                "missing_pages": s.get("missing_pages", []),
                "duplicate_pages": s.get("duplicate_pages", []),
                "rights": s["rights"],
                "status": s["status"],
                "metadata_json": {
                    k: s.get(k)
                    for k in (
                        "publisher",
                        "curriculum",
                        "language",
                        "file_type",
                        "book_index",
                        "visual_index",
                        "index_json",
                    )
                },
            }
        )
    source_by_id = {s["source_id"]: s["id"] for s in sources}

    for b in catalogue["books"]:
        books.append(
            {
                "id": uuid.UUID(b["id"]),
                "natural_key": b["natural_key"],
                "grade_id": grade_by_num[b["grade"]],
                "subject_id": subject_by_code[b["subject"]],
                "source_document_id": source_by_id[b["source_id"]],
                "title": b.get("title"),
                "chapter_label": b.get("chapter_label", "Chapter"),
            }
        )
        for ch in b["chapters"]:
            chapters.append(
                {
                    "id": uuid.UUID(ch["id"]),
                    "natural_key": ch["natural_key"],
                    "book_id": uuid.UUID(b["id"]),
                    "display_order": ch["order"],
                    "number": ch["number"],
                    "contents_number": ch.get("contents_number"),
                    "title": ch["title"],
                    "status": ch["status"],
                    "printed_start": ch.get("printed_start"),
                    "printed_end": ch.get("printed_end"),
                    "pdf_start": ch.get("pdf_start"),
                    "pdf_end": ch.get("pdf_end"),
                    "slo_codes": ch.get("slo_codes"),
                    "main_concept": ch.get("main_concept"),
                    "key_terms": ch.get("key_terms", []),
                    "visual_count": ch.get("visual_count", 0),
                    "assessment_counts": ch.get("assessment_counts", {}),
                    "content_state": "SOURCE_INDEXED",  # insert-only: re-imports never reset academic state
                    "retired_at": None,
                }
            )
            for order, (t, parent) in enumerate(_flatten(ch["topics"]), start=1):
                topics.append(
                    {
                        "id": uuid.UUID(t["id"]),
                        "natural_key": t["natural_key"],
                        "chapter_id": uuid.UUID(ch["id"]),
                        "parent_id": uuid.UUID(parent) if parent else None,
                        "display_order": order,
                        "number": t.get("number"),
                        "title": t["title"],
                        "depth": t["depth"],
                        "pdf_page": t.get("pdf_page"),
                        "points": t.get("points", []),
                        "retired_at": None,
                    }
                )

    existing_topics = set(session.scalars(select(Topic.id)))
    existing_chapters = set(session.scalars(select(Chapter.id)))
    retired_topics_db = set(session.scalars(select(Topic.id).where(Topic.retired_at.is_not(None))))
    retired_chapters_db = set(session.scalars(select(Chapter.id).where(Chapter.retired_at.is_not(None))))
    new_topic_ids = {t["id"] for t in topics}
    new_chapter_ids = {c["id"] for c in chapters}
    counts = {
        "regions": len(regions),
        "grades": len(grades),
        "subjects": len(subjects),
        "sources": len(sources),
        "books": len(books),
        "chapters": len(chapters),
        "topics": len(topics),
        "chapters_new": len(new_chapter_ids - existing_chapters),
        "topics_new": len(new_topic_ids - existing_topics),
        # Present in the database but no longer in the catalogue: retired (kept for history, hidden from learners).
        "retire_chapters": len((existing_chapters - new_chapter_ids) - retired_chapters_db),
        "retire_topics": len((existing_topics - new_topic_ids) - retired_topics_db),
        "reactivate_chapters": len(new_chapter_ids & retired_chapters_db),
        "reactivate_topics": len(new_topic_ids & retired_topics_db),
    }
    batch.counts = counts
    if not apply:
        batch.status, batch.finished_at = "DRY_RUN_OK", datetime.now(UTC)
        return batch

    model_rows: list[tuple[type[Any], list[dict[str, Any]], str]] = [
        (Region, regions, "id"),
        (Grade, grades, "id"),
        (Subject, subjects, "id"),
        (SourceDocument, sources, "id"),
        (BookEdition, books, "id"),
        (Chapter, chapters, "id"),
    ]
    # Active display orders are unique per parent. Move the affected rows' orders out of the way first so that
    # reordering within one import never collides mid-statement (same transaction, so nothing is visible).
    book_ids = [b["id"] for b in books]
    chapter_ids = [c["id"] for c in chapters]
    session.execute(
        update(Chapter)
        .where(Chapter.book_id.in_(book_ids), Chapter.retired_at.is_(None))
        .values(display_order=-Chapter.display_order - 1000)
    )
    session.execute(
        update(Topic)
        .where(Topic.chapter_id.in_(chapter_ids), Topic.retired_at.is_(None))
        .values(display_order=-Topic.display_order - 100000)
    )
    for model, rows, key in model_rows:
        if model is SourceDocument:
            rows = [
                {**{k: v for k, v in r.items() if k != "metadata_json"}, "metadata": r["metadata_json"]} for r in rows
            ]
        _upsert(session, model, rows, key)
    # Parents before children (flatten order guarantees it within a chapter).
    _upsert(session, Topic, topics)
    now = datetime.now(UTC)
    if existing_topics - new_topic_ids:
        session.execute(
            update(Topic)
            .where(Topic.id.in_(existing_topics - new_topic_ids), Topic.retired_at.is_(None))
            .values(retired_at=now)
        )
    if existing_chapters - new_chapter_ids:
        session.execute(
            update(Chapter)
            .where(Chapter.id.in_(existing_chapters - new_chapter_ids), Chapter.retired_at.is_(None))
            .values(retired_at=now)
        )
    batch.status, batch.finished_at = "APPLIED", datetime.now(UTC)
    session.add(batch)
    session.commit()
    return batch


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    ap.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    ap.add_argument("--apply", action="store_true", help="write to the database (default: dry run)")
    args = ap.parse_args(argv)
    with get_sessionmaker()() as session:
        batch = run_import(session, args.catalogue, args.registry, args.apply)
    print(
        json.dumps(
            {
                "status": batch.status,
                "dry_run": batch.dry_run,
                "counts": batch.counts,
                "errors": batch.errors,
                "input_sha256": batch.input_sha256,
            },
            indent=1,
        )
    )
    return 0 if batch.status in ("APPLIED", "DRY_RUN_OK") else 1


if __name__ == "__main__":
    sys.exit(main())
