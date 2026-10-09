"""Structured content import (roadmap P06.S2.T1/T2; IMPORT-01). See `docs/content-import.md` for the formats.

A batch is uploaded, validated in full and stored as a **preview** (dry run): per-row action (create, update,
unchanged, skip or error), row-level errors and warnings, and counts. Nothing touches the catalogue until the batch is
**committed**. Commit re-validates every row against the current database and writes all of its rows in one
transaction (the documented atomic boundary), or none. Every imported row becomes or updates a **draft** that goes
through the normal review, rights and publication gates; an import never submits, approves or publishes.

Idempotency: each row carries the author's stable `external_id`, unique per kind. Re-importing the same file finds
every row unchanged and writes nothing; a changed row updates the item's working draft (never a version in review or
published, which is skipped with a note to revise it in the studio). Committing a batch twice is refused; two batches
racing for the same new external ID cannot both create it (unique index), and the loser is told to preview again.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from portal_api.errors import Conflict, NotFound, TooLarge, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.content import blocks, kinds, workflow
from portal_api.modules.content.models import (
    Availability,
    ContentImportBatch,
    ContentImportRow,
    ContentItem,
    ContentVersion,
    ItemState,
    VersionStatus,
)
from portal_api.modules.curriculum.models import BookEdition, Chapter, Subject, Topic
from portal_api.modules.identity.deps import Principal
from portal_api.modules.identity.permissions import Permission, permissions_for

SCHEMA_VERSION = 1
IMPORT_KINDS = ("mcq", "lesson", "written")
MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 2000
PREVIEW_TTL = timedelta(hours=24)
EXTERNAL_ID_MAX = 120
CSV_COLUMNS = (
    "external_id",
    "chapter",
    "topic",
    "title",
    "stem",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct",
    "explanation",
    "difficulty",
    "estimated_seconds",
    "cognitive_demand",
    "source_document_id",
    "pdf_from",
    "pdf_to",
)


def _now() -> datetime:
    return datetime.now(UTC)


def _hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# ------------------------------------------------------------------ decoding
def _decode(data: bytes) -> str:
    if len(data) > MAX_BYTES:
        raise TooLarge(f"Import files can be at most {MAX_BYTES // (1024 * 1024)} MB.")
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise Unprocessable("The file must be UTF-8 encoded.", code_reason="ENCODING") from None


def _para(text: str) -> list[dict[str, Any]]:
    return [{"type": "paragraph", "text": text.strip()}] if text.strip() else []


def _csv_rows(text: str) -> tuple[str, list[dict[str, Any]]]:
    """The MCQ CSV template (plain paragraphs). Rich blocks, formulas and images need the JSON format."""
    reader = csv.DictReader(io.StringIO(text))
    header = [h.strip() for h in reader.fieldnames or []]
    missing = [
        c for c in ("external_id", "chapter", "title", "stem", "option_a", "option_b", "correct") if c not in header
    ]
    if missing:
        raise Unprocessable(f"Missing CSV columns: {', '.join(missing)}.", code_reason="CSV_HEADER")
    unknown = [h for h in header if h not in CSV_COLUMNS]
    if unknown:
        raise Unprocessable(f"Unknown CSV columns: {', '.join(unknown)}.", code_reason="CSV_HEADER")
    rows: list[dict[str, Any]] = []
    for raw in reader:
        r = {k.strip(): (v or "").strip() for k, v in raw.items() if k}
        options = [
            {"id": f"o{i + 1}", "blocks": _para(r.get(col, ""))}
            for i, col in enumerate(("option_a", "option_b", "option_c", "option_d"))
            if r.get(col, "")
        ]
        letter = r.get("correct", "").upper()
        correct = f"o{'ABCD'.index(letter) + 1}" if len(letter) == 1 and letter in "ABCD" else letter
        metadata: dict[str, Any] = {}
        for key in ("difficulty", "cognitive_demand"):
            if r.get(key):
                metadata[key] = r[key]
        if r.get("estimated_seconds"):
            metadata["estimated_seconds"] = (
                int(r["estimated_seconds"]) if r["estimated_seconds"].isdigit() else r["estimated_seconds"]
            )
        refs: list[Any] = []
        if r.get("source_document_id"):
            refs.append(
                {
                    "source_document_id": r["source_document_id"],
                    "pdf_from": int(r["pdf_from"]) if r.get("pdf_from", "").isdigit() else r.get("pdf_from"),
                    "pdf_to": int(r["pdf_to"]) if r.get("pdf_to", "").isdigit() else r.get("pdf_to"),
                }
            )
        rows.append(
            {
                "external_id": r.get("external_id", ""),
                "chapter": r.get("chapter", ""),
                "topic": r.get("topic") or None,
                "title": r.get("title", ""),
                "body": {
                    "stem": _para(r.get("stem", "")),
                    "options": options,
                    "correct_option_id": correct,
                    "explanation": {"correct": _para(r.get("explanation", ""))},
                    "metadata": metadata,
                },
                "source_refs": refs,
            }
        )
    return "mcq", rows


def _json_rows(text: str) -> tuple[str, list[dict[str, Any]]]:
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as e:
        raise Unprocessable(f"The file is not valid JSON (line {e.lineno}).", code_reason="JSON") from None
    if not isinstance(doc, dict):
        raise Unprocessable("The file must be a JSON object with schema_version, kind and items.", code_reason="JSON")
    if doc.get("schema_version") != SCHEMA_VERSION:
        raise Unprocessable(
            f"Unsupported schema_version; this portal reads version {SCHEMA_VERSION}.", code_reason="SCHEMA_VERSION"
        )
    kind = doc.get("kind")
    if kind not in IMPORT_KINDS:
        raise Unprocessable(f"kind must be one of: {', '.join(IMPORT_KINDS)}.", code_reason="KIND")
    items = doc.get("items")
    if not isinstance(items, list):
        raise Unprocessable("items must be a list.", code_reason="JSON")
    return str(kind), [i if isinstance(i, dict) else {"_invalid": True} for i in items]


def parse_file(data: bytes, fmt: str) -> tuple[str, list[dict[str, Any]]]:
    text = _decode(data)
    kind, rows = _csv_rows(text) if fmt == "csv" else _json_rows(text)
    if not rows:
        raise Unprocessable("The file has no rows.", code_reason="EMPTY")
    if len(rows) > MAX_ROWS:
        raise TooLarge(f"A batch can have at most {MAX_ROWS} rows; split the file.")
    return kind, rows


# ------------------------------------------------------------------ validation
def _chapter(db: Session, ref: str) -> Chapter | None:
    try:
        return db.get(Chapter, uuid.UUID(ref))
    except ValueError:
        return db.scalar(select(Chapter).where(Chapter.natural_key == ref))


def _topic(db: Session, ref: str, chapter: Chapter) -> Topic | None:
    try:
        t = db.get(Topic, uuid.UUID(ref))
    except ValueError:
        t = db.scalar(select(Topic).where(Topic.natural_key == ref))
    return t if t is not None and t.chapter_id == chapter.id and t.retired_at is None else None


def _validate_row(
    db: Session, who: Principal, kind: str, raw: dict[str, Any], scope_cache: dict[Any, bool]
) -> dict[str, Any]:
    """One row's action, errors, warnings and normalised payload. Writes nothing."""
    errors: list[str] = []
    warnings: list[str] = []
    ext = raw.get("external_id")
    if raw.get("_invalid"):
        return {"external_id": None, "action": "error", "errors": ["Each item must be a JSON object."], "warnings": []}
    if not isinstance(ext, str) or not ext.strip() or len(ext.strip()) > EXTERNAL_ID_MAX:
        errors.append(f"external_id is required (at most {EXTERNAL_ID_MAX} characters).")
        ext = None
    else:
        ext = ext.strip()
    title = raw.get("title")
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 300:
        errors.append("title is required (at most 300 characters).")
    chapter = _chapter(db, str(raw.get("chapter") or ""))
    payload: dict[str, Any] = {}
    if chapter is None or chapter.retired_at is not None:
        errors.append("chapter: unknown or retired chapter (use its stable key or ID).")
    else:
        book = db.get(BookEdition, chapter.book_id)
        subject = db.get(Subject, book.subject_id) if book else None
        if book is None or subject is None or not subject.active:
            errors.append("chapter: outside the current academic scope.")
        else:
            key = (book.grade.number, subject.code)
            if key not in scope_cache:
                roles = workflow.roles_in_scope(db, who.user.id, *key)
                scope_cache[key] = Permission.draft_content in permissions_for(roles)
            if not scope_cache[key]:
                errors.append(f"You can't draft Class {key[0]} {key[1]} content.")
            topic_id = None
            if raw.get("topic"):
                topic = _topic(db, str(raw["topic"]), chapter)
                if topic is None:
                    errors.append("topic: not a current topic of this chapter.")
                else:
                    topic_id = str(topic.id)
            body, body_errors, types = kinds.get(kind).parse_draft(raw.get("body"))
            errors += [f"body: {e}" for e in body_errors]
            s_err, s_warn, refs = workflow.check_sources(db, chapter, raw.get("source_refs", []))
            errors += s_err
            warnings += s_warn
            if not raw.get("source_refs"):
                warnings.append("No source page references yet; they are required before publication.")
            if body is not None:
                pub = kinds.get(kind).validate(body, True)
                warnings += [f"before publication: {e}" for e in pub.errors]
                payload = {
                    "chapter_id": str(chapter.id),
                    "topic_id": topic_id,
                    "title": title.strip() if isinstance(title, str) else "",
                    "body": body,
                    "block_types": types,
                    "source_refs": refs,
                }
    if errors:
        return {"external_id": ext, "action": "error", "errors": errors, "warnings": warnings}
    existing = db.scalar(select(ContentItem).where(ContentItem.kind == kind, ContentItem.external_ref == ext))
    digest = _hash(payload)
    if existing is None:
        action = "create"
    elif existing.state not in (ItemState.draft.value, ItemState.changes_requested.value):
        action = "skip"
        warnings.append(f"Already {existing.state.replace('_', ' ')}; start a revision in the studio to change it.")
    elif existing.import_hash == digest:
        action = "unchanged"
    elif str(existing.chapter_id) != payload["chapter_id"]:
        return {
            "external_id": ext,
            "action": "error",
            "errors": ["This external_id already belongs to another chapter; items don't move between chapters."],
            "warnings": warnings,
        }
    else:
        action = "update"
    return {
        "external_id": ext,
        "action": action,
        "errors": [],
        "warnings": warnings,
        "item_id": str(existing.id) if existing else None,
        "payload": payload,
        "payload_hash": digest,
    }


def preview(db: Session, who: Principal, data: bytes, *, fmt: str, filename: str) -> ContentImportBatch:
    if fmt not in ("json", "csv"):
        raise Unprocessable("Choose json or csv.")
    kind, raw_rows = parse_file(data, fmt)
    scope_cache: dict[Any, bool] = {}
    results = [_validate_row(db, who, kind, r, scope_cache) for r in raw_rows]
    seen: dict[str, int] = {}
    stems: dict[str, int] = {}
    for n, r in enumerate(results, start=1):
        ext = r.get("external_id")
        if ext and ext in seen:
            r["action"] = "error"
            r["errors"] = [*r["errors"], f"Duplicate external_id; first used on row {seen[ext]}."]
        elif ext:
            seen[ext] = n
        body = (r.get("payload") or {}).get("body") or {}
        stem = json.dumps(body.get("stem") or body.get("blocks") or [], sort_keys=True).lower()
        if stem not in ("[]", "") and r["action"] != "error":
            if stem in stems:
                r["warnings"] = [*r["warnings"], f"Same text as row {stems[stem]}; check this isn't a duplicate."]
            else:
                stems[stem] = n
    counts: dict[str, int] = {}
    for r in results:
        counts[r["action"]] = counts.get(r["action"], 0) + 1
    batch = ContentImportBatch(
        id=uuid.uuid4(),
        kind=kind,
        format=fmt,
        filename=filename[:200],
        sha256=hashlib.sha256(data).hexdigest(),
        schema_version=SCHEMA_VERSION,
        status="previewed",
        counts=counts,
        created_by=who.user.id,
        expires_at=_now() + PREVIEW_TTL,
    )
    db.add(batch)
    db.flush()
    for n, r in enumerate(results, start=1):
        db.add(
            ContentImportRow(
                batch_id=batch.id,
                row_number=n,
                external_id=r.get("external_id"),
                action=r["action"],
                errors=r["errors"],
                warnings=r["warnings"],
                payload=r.get("payload") or {},
                payload_hash=r.get("payload_hash"),
                item_id=uuid.UUID(r["item_id"]) if r.get("item_id") else None,
            )
        )
    record(
        db,
        actor=who.user.id,
        action="content.import_previewed",
        target_type="content_import_batch",
        target_id=str(batch.id),
        details={"kind": kind, "format": fmt, "sha256": batch.sha256, "counts": counts},
    )
    db.commit()
    db.refresh(batch)
    return batch


# ------------------------------------------------------------------ commit
def _own_batch(db: Session, who: Principal, batch_id: uuid.UUID, *, for_update: bool = False) -> ContentImportBatch:
    stmt = select(ContentImportBatch).where(ContentImportBatch.id == batch_id)
    if for_update:
        stmt = stmt.with_for_update()
    batch = db.scalar(stmt)
    if batch is None or batch.created_by != who.user.id:
        raise NotFound("Import not found.")
    return batch


def rows(db: Session, batch_id: uuid.UUID) -> list[ContentImportRow]:
    return list(
        db.scalars(
            select(ContentImportRow).where(ContentImportRow.batch_id == batch_id).order_by(ContentImportRow.row_number)
        )
    )


def get_batch(db: Session, who: Principal, batch_id: uuid.UUID) -> ContentImportBatch:
    return _own_batch(db, who, batch_id)


def list_batches(db: Session, who: Principal) -> list[ContentImportBatch]:
    return list(
        db.scalars(
            select(ContentImportBatch)
            .where(ContentImportBatch.created_by == who.user.id)
            .order_by(ContentImportBatch.created_at.desc())
            .limit(50)
        )
    )


def discard(db: Session, who: Principal, batch_id: uuid.UUID) -> ContentImportBatch:
    batch = _own_batch(db, who, batch_id, for_update=True)
    if batch.status != "previewed":
        raise Conflict(f"This import is already {batch.status}.")
    batch.status = "discarded"
    db.commit()
    return batch


def commit(db: Session, who: Principal, batch_id: uuid.UUID) -> ContentImportBatch:
    batch = _own_batch(db, who, batch_id, for_update=True)
    if batch.status != "previewed":
        raise Conflict(f"This import is already {batch.status}.")
    if batch.expires_at <= _now():
        raise Conflict("This preview is more than a day old. Upload the file again to preview it.")
    stored = rows(db, batch.id)
    if any(r.action == "error" for r in stored):
        raise Conflict("Fix the rows with errors and preview the file again; nothing was imported.")
    scope_cache: dict[Any, bool] = {}
    written = {"created": 0, "updated": 0}
    for r in stored:
        if r.action not in ("create", "update"):
            continue
        # Re-check against the current database: another batch or editor may have changed things since the preview.
        fresh = _validate_row(db, who, batch.kind, _row_input(r), scope_cache)
        if fresh["action"] != r.action or fresh.get("payload_hash") != r.payload_hash:
            db.rollback()
            raise Conflict(
                f"Row {r.row_number} ({r.external_id}) changed since the preview; preview the file again.",
                row=r.row_number,
            )
        if r.action == "create":
            item_id = _create(db, who, batch, r)
            r.item_id = item_id
            written["created"] += 1
        else:
            _update(db, who, batch, r)
            written["updated"] += 1
    batch.status = "committed"
    batch.committed_at = _now()
    batch.counts = {**batch.counts, **{f"written_{k}": v for k, v in written.items()}}
    record(
        db,
        actor=who.user.id,
        action="content.import_committed",
        target_type="content_import_batch",
        target_id=str(batch.id),
        details={"kind": batch.kind, "sha256": batch.sha256, **written},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflict("Another import created some of these items at the same time; preview the file again.") from None
    db.refresh(batch)
    return batch


def _row_input(r: ContentImportRow) -> dict[str, Any]:
    p = r.payload
    return {
        "external_id": r.external_id,
        "chapter": p["chapter_id"],
        "topic": p.get("topic_id"),
        "title": p["title"],
        "body": p["body"],
        "source_refs": p["source_refs"],
    }


def _create(db: Session, who: Principal, batch: ContentImportBatch, r: ContentImportRow) -> uuid.UUID:
    p = r.payload
    chapter = db.get(Chapter, uuid.UUID(p["chapter_id"]))
    assert chapter is not None
    book = db.get(BookEdition, chapter.book_id)
    assert book is not None
    subject = db.get(Subject, book.subject_id)
    assert subject is not None
    item = ContentItem(
        id=uuid.uuid4(),
        kind=batch.kind,
        chapter_id=chapter.id,
        topic_id=uuid.UUID(p["topic_id"]) if p.get("topic_id") else None,
        grade_number=book.grade.number,
        subject_code=subject.code,
        title=p["title"],
        state=ItemState.draft.value,
        availability=Availability.unpublished.value,
        created_by=who.user.id,
        external_ref=r.external_id,
        import_hash=r.payload_hash,
    )
    if batch.kind in ("mcq", "written"):
        item.family_id = item.id
    version = ContentVersion(
        id=uuid.uuid4(),
        item_id=item.id,
        number=1,
        status=VersionStatus.draft.value,
        revision=1,
        content_schema_version=blocks.CONTENT_SCHEMA_VERSION,
        body=p["body"],
        block_types=p["block_types"],
        source_refs=p["source_refs"],
        created_by=who.user.id,
        contributors=[str(who.user.id)],
        updated_by=who.user.id,
    )
    db.add(item)
    db.flush()
    db.add(version)
    db.flush()
    item.working_version_id = version.id
    record(
        db,
        actor=who.user.id,
        action="content.imported",
        target_type="content_item",
        target_id=str(item.id),
        details={"batch": str(batch.id), "row": r.row_number, "external_id": r.external_id, "created": True},
    )
    return item.id


def _update(db: Session, who: Principal, batch: ContentImportBatch, r: ContentImportRow) -> None:
    item = workflow.get_item(db, r.item_id, for_update=True) if r.item_id else None
    if item is None or item.state not in (ItemState.draft.value, ItemState.changes_requested.value):
        raise Conflict(f"Row {r.row_number} ({r.external_id}) is no longer a draft; preview the file again.")
    p = r.payload
    version = db.get(ContentVersion, item.working_version_id)
    assert version is not None
    version.body = p["body"]
    version.block_types = p["block_types"]
    version.source_refs = p["source_refs"]
    version.revision += 1
    version.updated_by = who.user.id
    version.updated_at = _now()
    if str(who.user.id) not in version.contributors:
        version.contributors = [*version.contributors, str(who.user.id)]
    item.title = p["title"]
    item.topic_id = uuid.UUID(p["topic_id"]) if p.get("topic_id") else None
    item.import_hash = r.payload_hash
    item.updated_at = _now()
    if item.state == ItemState.changes_requested.value:
        item.state = ItemState.draft.value
        version.status = VersionStatus.draft.value
    record(
        db,
        actor=who.user.id,
        action="content.imported",
        target_type="content_item",
        target_id=str(item.id),
        details={"batch": str(batch.id), "row": r.row_number, "external_id": r.external_id, "created": False},
    )


def report_csv(db: Session, who: Principal, batch_id: uuid.UUID) -> str:
    """The downloadable correction report: one line per row with its action, errors and warnings."""
    batch = _own_batch(db, who, batch_id)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["row", "external_id", "action", "errors", "warnings", "item_id"])
    for r in rows(db, batch.id):
        w.writerow(
            [r.row_number, r.external_id or "", r.action, " | ".join(r.errors), " | ".join(r.warnings), r.item_id or ""]
        )
    return buf.getvalue()
