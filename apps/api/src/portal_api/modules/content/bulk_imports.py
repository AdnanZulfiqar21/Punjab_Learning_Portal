"""Bulk imports checked and committed by a worker (P06.S2.T1 "stream large jobs in bulk workers"; IMPORT-BULK-01).

A file too large for a preview inside a request (over 5 MB or 2,000 rows) is streamed to private storage and queued:
at most 50 MB and 20,000 rows. A separate worker process (``portal-import-worker``) claims a queued batch with
``SKIP LOCKED`` and a lease and checks its rows with exactly the rules of a preview (`imports._validate_row`). Each
chunk of rows is stored in its own short transaction and extends the lease, so a crashed worker's lease expires and
another worker resumes after the last stored row; nothing is checked twice or skipped. When every row is stored it
marks duplicates across the whole file and the batch becomes an ordinary preview (counts, row errors and warnings,
the correction report), which expires like any other.

Committing a preview of more than 2,000 rows is queued for the worker too. The worker re-checks and writes every row
in **one transaction**, or none (the documented boundary for bulk batches); a row that changed since the preview, or
an item another import created meanwhile, fails the batch with the reason and writes nothing.

The uploaded file is deleted as soon as its rows are stored, or when the batch fails or is discarded. A queued batch
whose file is never processed keeps it until it is discarded.
"""

from __future__ import annotations

import contextlib
import os
import socket
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from portal_api.errors import AppError, Conflict, TooMany, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.content import imports
from portal_api.modules.content.models import ContentImportBatch, ContentImportRow
from portal_api.modules.identity.deps import Principal
from portal_api.modules.identity.models import AppUser

BULK = imports.Limits(max_bytes=50 * 1024 * 1024, max_rows=20_000, max_part=100 * 1024 * 1024)
SYNC_COMMIT_ROWS = 2000  # larger previews commit in the worker, never inside a request
CHUNK = 250
LEASE = timedelta(minutes=2)
ACTIVE = ("queued", "validating", "committing")


# ------------------------------------------------------------------ storage (private, never served)
def _root() -> Path:
    from portal_api.config import get_settings

    base = Path(os.environ.get("PORTAL_IMPORT_DIR") or Path(get_settings().evidence_dir).parent / "imports")
    if not base.is_absolute():
        base = Path(__file__).resolve().parents[4] / base
    base.mkdir(parents=True, exist_ok=True)
    return base


def new_upload_path() -> tuple[str, Path]:
    key = f"{uuid.uuid4()}.upload"
    return key, _root() / key


def _remove(key: str | None) -> None:
    if key:
        with contextlib.suppress(OSError):  # a file left behind holds no content and is never served
            (_root() / key).unlink(missing_ok=True)


def _now(db: Session) -> datetime:
    now: datetime = db.execute(
        select(func.clock_timestamp())
    ).scalar_one()  # the database clock, not the transaction start
    return now


# ------------------------------------------------------------------ requests
def enqueue(db: Session, who: Principal, *, fmt: str, filename: str, key: str, sha256: str) -> ContentImportBatch:
    if fmt not in ("json", "csv", "xlsx"):
        _remove(key)
        raise Unprocessable("Choose json, csv or xlsx.")
    recent = db.scalar(
        select(func.count())
        .select_from(ContentImportBatch)
        .where(
            ContentImportBatch.created_by == who.user.id,
            ContentImportBatch.created_at > func.now() - timedelta(hours=1),
        )
    )
    if (recent or 0) >= imports.PREVIEWS_PER_HOUR:  # the same budget as previews in a request
        _remove(key)
        raise TooMany(
            f"You've previewed {imports.PREVIEWS_PER_HOUR} imports in the last hour. Please wait before the next."
        )
    now = _now(db)
    batch = ContentImportBatch(
        id=uuid.uuid4(),
        kind="pending",  # known once the worker has read the file
        format=fmt,
        filename=filename[:200],
        sha256=sha256,
        schema_version=imports.SCHEMA_VERSION,
        status="queued",
        counts={},
        created_by=who.user.id,
        expires_at=now + imports.PREVIEW_TTL,
        file_key=key,
    )
    db.add(batch)
    record(db, actor=who.user.id, action="content.import_queued", target_type="content_import_batch",
           target_id=str(batch.id), details={"format": fmt, "sha256": sha256})  # fmt: skip
    db.commit()
    db.refresh(batch)
    return batch


def queue_commit(db: Session, who: Principal, batch: ContentImportBatch) -> ContentImportBatch:
    """Hand a checked, error-free preview of many rows to the worker (called with the batch locked)."""
    batch.status = "committing"
    batch.lease_owner = batch.lease_expires_at = None
    record(db, actor=who.user.id, action="content.import_commit_queued", target_type="content_import_batch",
           target_id=str(batch.id), details={"rows": batch.rows_total})  # fmt: skip
    db.commit()
    db.refresh(batch)
    return batch


def discard_queued(batch: ContentImportBatch) -> None:
    _remove(batch.file_key)
    batch.file_key = None


# ------------------------------------------------------------------ worker
def _claim(db: Session, owner: str) -> tuple[uuid.UUID, str] | None:
    now = _now(db)
    batch = db.scalar(
        select(ContentImportBatch)
        .where(
            ContentImportBatch.status.in_(ACTIVE),
            (ContentImportBatch.lease_expires_at.is_(None)) | (ContentImportBatch.lease_expires_at < now),
        )
        .order_by(ContentImportBatch.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if batch is None:
        db.rollback()
        return None
    if batch.status == "queued":
        batch.status = "validating"
    batch.lease_owner, batch.lease_expires_at = owner, now + LEASE
    claimed = (batch.id, batch.status)
    db.commit()
    return claimed


def _actor(db: Session, user_id: uuid.UUID) -> Principal:
    """The import's author, for the scope checks and audit entries made on their behalf. Roles are read from the
    database on every check, so an author whose role was revoked meanwhile gets scope errors, not a write."""

    class _Author:
        def __init__(self, user: AppUser) -> None:
            self.user = user

    user = db.get(AppUser, user_id)
    assert user is not None
    return cast(Principal, _Author(user))


def _locked(db: Session, batch_id: uuid.UUID, owner: str, status: str) -> ContentImportBatch | None:
    batch = db.scalar(select(ContentImportBatch).where(ContentImportBatch.id == batch_id).with_for_update())
    if batch is None or batch.status != status or batch.lease_owner != owner:
        db.rollback()  # discarded, or another worker took over after our lease ran out
        return None
    return batch


def _fail(db: Session, batch_id: uuid.UUID, reason: str) -> None:
    batch = db.scalar(select(ContentImportBatch).where(ContentImportBatch.id == batch_id).with_for_update())
    assert batch is not None
    _remove(batch.file_key)
    batch.status, batch.failure, batch.file_key = "failed", reason[:1000], None
    batch.lease_owner = batch.lease_expires_at = None
    record(db, actor=batch.created_by, action="content.import_failed", target_type="content_import_batch",
           target_id=str(batch.id), details={"reason": reason[:300]})  # fmt: skip
    db.commit()


def _check_rows(db: Session, batch_id: uuid.UUID, owner: str) -> str:
    batch = db.get(ContentImportBatch, batch_id)
    assert batch is not None
    try:
        data = (_root() / (batch.file_key or "missing")).read_bytes()
    except OSError:
        _fail(db, batch_id, "The uploaded file is missing. Upload it again.")
        return "failed"
    try:
        kind, raw_rows = imports.parse_file(data, batch.format, BULK)
    except AppError as e:
        db.rollback()
        _fail(db, batch_id, e.detail)
        return "failed"
    del data
    who = _actor(db, batch.created_by)
    done = db.scalar(select(func.count()).select_from(ContentImportRow).where(ContentImportRow.batch_id == batch_id))
    db.commit()
    scope_cache: dict[Any, bool] = {}
    for start in range(done or 0, len(raw_rows), CHUNK):
        locked = _locked(db, batch_id, owner, "validating")
        if locked is None:
            return "stopped"
        locked.kind, locked.rows_total = kind, len(raw_rows)
        chunk = raw_rows[start : start + CHUNK]
        for n, raw in enumerate(chunk, start=start + 1):
            r = imports._validate_row(db, who, kind, raw, scope_cache)
            db.add(
                ContentImportRow(
                    batch_id=batch_id,
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
        locked.rows_checked = start + len(chunk)
        locked.lease_expires_at = _now(db) + LEASE
        db.commit()  # this chunk is durable: a worker that dies now resumes after it

    locked = _locked(db, batch_id, owner, "validating")
    if locked is None:
        return "stopped"
    stored = imports.rows(db, batch_id)
    results: list[dict[str, Any]] = [
        {
            "external_id": row.external_id,
            "action": row.action,
            "errors": list(row.errors),
            "warnings": list(row.warnings),
            "payload": row.payload,
        }
        for row in stored
    ]
    imports.mark_duplicates(results)
    for row, res in zip(stored, results, strict=True):
        if res["action"] != row.action or res["errors"] != row.errors or res["warnings"] != row.warnings:
            row.action, row.errors, row.warnings = res["action"], res["errors"], res["warnings"]
    now = _now(db)
    locked.kind, locked.rows_total, locked.rows_checked = kind, len(raw_rows), len(raw_rows)
    locked.status, locked.counts = "previewed", imports.count_actions(results)
    locked.expires_at = now + imports.PREVIEW_TTL  # a day to review it, from when it is ready
    locked.lease_owner = locked.lease_expires_at = None
    key, locked.file_key = locked.file_key, None
    record(db, actor=locked.created_by, action="content.import_previewed", target_type="content_import_batch",
           target_id=str(batch_id), details={"kind": kind, "format": locked.format, "sha256": locked.sha256,
                                               "counts": locked.counts, "bulk": True})  # fmt: skip
    db.commit()
    _remove(key)
    return "previewed"


def _commit_rows(db: Session, batch_id: uuid.UUID, owner: str) -> str:
    locked = _locked(db, batch_id, owner, "committing")
    if locked is None:
        return "stopped"
    who = _actor(db, locked.created_by)
    stored = imports.rows(db, batch_id)
    if any(r.action == "error" for r in stored):
        db.rollback()
        _fail(db, batch_id, "The preview has rows with errors; nothing was imported.")
        return "failed"
    try:
        imports.apply_commit(db, who, locked, stored)  # one transaction: every row, or none
        locked.lease_owner = locked.lease_expires_at = None
        db.commit()
    except Conflict as e:
        db.rollback()
        _fail(db, batch_id, f"{e.detail} Nothing was imported.")
        return "failed"
    except IntegrityError:
        db.rollback()
        _fail(db, batch_id, "Another import created some of these items at the same time; nothing was imported.")
        return "failed"
    return "committed"


def run_one(db: Session, owner: str) -> dict[str, Any] | None:
    """Claim one batch and take it as far as it goes. Returns what happened, or None when nothing is waiting."""
    claimed = _claim(db, owner)
    if claimed is None:
        return None
    batch_id, status = claimed
    outcome = _check_rows(db, batch_id, owner) if status == "validating" else _commit_rows(db, batch_id, owner)
    return {"batch": str(batch_id), "outcome": outcome}


def work(db: Session, owner: str | None = None, max_jobs: int | None = None) -> int:
    """Drain the queue (tests, the CLI). Returns how many batches were handled."""
    owner = owner or f"{socket.gethostname()}:{os.getpid()}"
    n = 0
    while max_jobs is None or n < max_jobs:
        if run_one(db, owner) is None:
            break
        n += 1
    return n


def worker_main(argv: list[str] | None = None) -> int:
    """portal-import-worker [--once] [--interval S]: checks and commits bulk content imports."""
    import argparse

    p = argparse.ArgumentParser(prog="portal-import-worker")
    p.add_argument("--once", action="store_true", help="drain the queue once and exit")
    p.add_argument("--interval", type=float, default=2.0)
    args = p.parse_args(argv)
    owner = f"{socket.gethostname()}:{os.getpid()}"
    print(f"import worker {owner} started", flush=True)
    while True:
        with get_sessionmaker()() as db:  # a fresh session per drain: no connection kept across idle waits
            n = work(db, owner)
        if n:
            print(f"handled {n} import batch(es)", flush=True)
        if args.once:
            return 0
        time.sleep(args.interval)
