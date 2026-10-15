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

**Claims (OCT14-02).** Every claim carries a fresh token in ``lease_owner``. Every write a worker makes (progress,
the finished preview, the commit, a failure, file cleanup and its audit entry) first re-reads the batch under a row
lock, straight from the database (``populate_existing``: sessions keep objects across commits), and goes ahead only
if the batch still has that worker's token and the expected status. A worker whose lease ran out and was taken over
stops without touching the batch, its file or the audit trail. A file is deleted only after the state change that
releases it has committed.

**Failures (OCT14-03).** Bad input (an unreadable or invalid file, an author no longer allowed to import, a preview
out of date) fails the batch once, with the reason. Anything else (the database, storage, a bug) is not the author's
fault: the batch is released for another try after a growing pause, and fails with a clear reason only after
``MAX_ATTEMPTS`` claims, so a poison job can't loop forever or stop the rest of the queue.

**Authority (OCT14-05).** Work runs on the author's behalf only while their account is active and, row by row, while
they still hold a content role for the class and subject (re-read for every chunk and again at commit). A suspended,
deleted or de-scoped author's queued work fails with the reason; nothing new is written.
"""

from __future__ import annotations

import contextlib
import os
import socket
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from portal_api.budget import bulk_pause_reason, bulk_paused_now, process_class
from portal_api.db import get_sessionmaker
from portal_api.errors import AppError, Conflict, TooMany, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.content import imports
from portal_api.modules.content.models import ContentImportBatch, ContentImportRow
from portal_api.modules.identity.deps import Principal
from portal_api.modules.identity.models import AppUser
from portal_api.observability import bind_correlation

BULK = imports.Limits(max_bytes=50 * 1024 * 1024, max_rows=20_000, max_part=100 * 1024 * 1024)
SYNC_COMMIT_ROWS = 2000  # larger previews commit in the worker, never inside a request
CHUNK = 250
LEASE = timedelta(minutes=2)
ACTIVE = ("queued", "validating", "committing")
MAX_ATTEMPTS = 5  # claims per phase before a batch that keeps failing for unexpected reasons is failed
RETRY_PAUSE = timedelta(seconds=30)  # doubled per attempt, at most RETRY_PAUSE_MAX
RETRY_PAUSE_MAX = timedelta(minutes=15)


class Stop(Exception):
    """This worker no longer holds the batch (taken over after its lease ran out, or discarded): touch nothing."""


class Refused(Exception):
    """A permanent reason this batch can't go on; the author is told why and nothing new is written."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


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
    batch.attempts, batch.last_error = 0, None  # a new phase gets its own attempts
    record(db, actor=who.user.id, action="content.import_commit_queued", target_type="content_import_batch",
           target_id=str(batch.id), details={"rows": batch.rows_total})  # fmt: skip
    db.commit()
    db.refresh(batch)
    return batch


def remove_upload(key: str | None) -> None:
    """Delete an upload once the state change that released it has committed."""
    _remove(key)


# ------------------------------------------------------------------ worker
@dataclass(frozen=True)
class Claim:
    batch_id: uuid.UUID
    status: str  # "validating" or "committing"
    token: str  # this claim's lease_owner; every write checks it
    attempts: int
    correlation_id: str | None = None  # CORRELATION-01: the upload request's


def _claim(db: Session, owner: str) -> Claim | None:
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
        .execution_options(populate_existing=True)
    )
    if batch is None:
        db.rollback()
        return None
    if batch.status == "queued":
        batch.status = "validating"
    token = f"{owner[:80]}#{uuid.uuid4().hex[:16]}"
    batch.lease_owner, batch.lease_expires_at = token, now + LEASE
    batch.attempts = (batch.attempts or 0) + 1
    claim = Claim(batch.id, batch.status, token, batch.attempts, batch.correlation_id)
    db.commit()
    return claim


def _locked(db: Session, claim: Claim) -> ContentImportBatch:
    """The batch, locked and re-read from the database, if this claim still holds it; otherwise Stop."""
    batch = db.scalar(
        select(ContentImportBatch)
        .where(ContentImportBatch.id == claim.batch_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if batch is None or batch.status != claim.status or batch.lease_owner != claim.token:
        db.rollback()
        raise Stop
    return batch


def _actor(db: Session, user_id: uuid.UUID) -> Principal:
    """The import's author, for the scope checks and audit entries made on their behalf, only while their account is
    active (a suspended or deleted account can't sign in, so its queued work can't write either). Scoped roles are
    read from the database on every check."""

    class _Author:
        def __init__(self, user: AppUser) -> None:
            self.user = user

    user = db.scalar(select(AppUser).where(AppUser.id == user_id).execution_options(populate_existing=True))
    if user is None or user.status != "active":
        raise Refused("The account that uploaded this import is no longer active, so nothing was imported.")
    return cast(Principal, _Author(user))


def _fail(db: Session, claim: Claim, reason: str) -> str:
    """End the batch as failed, with the reason, if this claim still holds it. Returns the outcome."""
    try:
        batch = _locked(db, claim)
    except Stop:
        return "stopped"
    key = batch.file_key
    batch.status, batch.failure, batch.file_key = "failed", reason[:1000], None
    batch.lease_owner = batch.lease_expires_at = None
    record(db, actor=batch.created_by, action="content.import_failed", target_type="content_import_batch",
           target_id=str(batch.id), details={"reason": reason[:300], "attempts": claim.attempts})  # fmt: skip
    db.commit()
    _remove(key)  # only now: the batch no longer names the file
    return "failed"


def _retry_later(db: Session, claim: Claim, error: BaseException) -> str:
    """Something unexpected (the database, storage, a bug): release the batch for another try after a pause, or fail
    it once it has had MAX_ATTEMPTS claims. Never reported to the author as a problem with their file."""
    detail = f"{type(error).__name__}: {error}"[:1000]
    if claim.attempts >= MAX_ATTEMPTS:
        return _fail(
            db,
            claim,
            f"This import couldn't be processed after {claim.attempts} tries because of a problem on our side, so "
            "nothing was imported. Please upload it again later; if it keeps happening, contact support.",
        )
    try:
        batch = _locked(db, claim)
    except Stop:
        return "stopped"
    pause = min(RETRY_PAUSE * (2 ** (claim.attempts - 1)), RETRY_PAUSE_MAX)
    batch.lease_owner, batch.lease_expires_at = None, _now(db) + pause
    batch.last_error = detail
    db.commit()
    return "retry"


def _check_rows(db: Session, claim: Claim) -> str:
    batch = _locked(db, claim)
    key, fmt, author = batch.file_key, batch.format, batch.created_by
    db.commit()  # nothing slow happens under a lock
    try:
        data = (_root() / (key or "missing")).read_bytes()
    except FileNotFoundError:
        raise Refused("The uploaded file is missing. Upload it again.") from None
    try:
        kind, raw_rows = imports.parse_file(data, fmt, BULK)
    except AppError as e:
        raise Refused(e.detail) from None
    del data
    done = db.scalar(
        select(func.count()).select_from(ContentImportRow).where(ContentImportRow.batch_id == claim.batch_id)
    )
    db.commit()
    for start in range(done or 0, len(raw_rows), CHUNK):
        who = _actor(db, author)  # re-read for every chunk: a suspension takes effect at the next chunk
        locked = _locked(db, claim)
        locked.kind, locked.rows_total = kind, len(raw_rows)
        scope_cache: dict[Any, bool] = {}  # per chunk, so a revoked role is seen at the next chunk
        chunk = raw_rows[start : start + CHUNK]
        for n, raw in enumerate(chunk, start=start + 1):
            r = imports._validate_row(db, who, kind, raw, scope_cache)
            db.add(
                ContentImportRow(
                    batch_id=claim.batch_id,
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

    _actor(db, author)
    locked = _locked(db, claim)
    stored = imports.rows(db, claim.batch_id)
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
    locked.attempts, locked.last_error = 0, None
    key, locked.file_key = locked.file_key, None
    record(db, actor=locked.created_by, action="content.import_previewed", target_type="content_import_batch",
           target_id=str(claim.batch_id), details={"kind": kind, "format": locked.format, "sha256": locked.sha256,
                                                     "counts": locked.counts, "bulk": True})  # fmt: skip
    db.commit()
    _remove(key)
    return "previewed"


def _commit_rows(db: Session, claim: Claim) -> str:
    locked = _locked(db, claim)
    who = _actor(db, locked.created_by)
    stored = imports.rows(db, claim.batch_id)
    if any(r.action == "error" for r in stored):
        raise Refused("The preview has rows with errors; nothing was imported.")
    try:
        imports.apply_commit(db, who, locked, stored)  # one transaction: every row, or none
        locked.lease_owner = locked.lease_expires_at = None
        locked.last_error = None
        db.commit()
    except Conflict as e:
        db.rollback()
        raise Refused(f"{e.detail} Nothing was imported.") from None
    except IntegrityError:
        db.rollback()
        raise Refused("Another import created some of these items at the same time; nothing was imported.") from None
    return "committed"


def run_one(db: Session, owner: str) -> dict[str, Any] | None:
    """Claim one batch and take it as far as it goes. Returns what happened, or None when nothing is waiting."""
    claim = _claim(db, owner)
    if claim is None:
        return None
    with bind_correlation(claim.correlation_id):  # CORRELATION-01: audit entries and logs trace to the upload
        try:
            if claim.attempts > MAX_ATTEMPTS:  # it kept failing, or kept killing its worker, before finishing
                outcome = _retry_later(db, claim, RuntimeError("no attempts left"))
            elif claim.status == "validating":
                outcome = _check_rows(db, claim)
            else:
                outcome = _commit_rows(db, claim)
        except Stop:
            outcome = "stopped"
        except Refused as r:
            db.rollback()
            outcome = _fail(db, claim, r.reason)
        except Exception as e:  # one batch's trouble must not stop the queue: it is retried, then failed
            db.rollback()
            print(
                f"import batch {claim.batch_id} (correlation {claim.correlation_id}): {type(e).__name__}: {e}",
                file=sys.stderr,
                flush=True,
            )
            try:
                outcome = _retry_later(db, claim, e)
            except Exception:  # the database itself is down: the lease runs out and the batch is claimed again
                db.rollback()
                outcome = "retry"
        return {"batch": str(claim.batch_id), "outcome": outcome}


def work(db: Session, owner: str | None = None, max_jobs: int | None = None) -> int:
    """Drain the queue (tests, the CLI). Returns how many batches were handled."""
    owner = owner or f"{socket.gethostname()}:{os.getpid()}"
    n = 0
    while max_jobs is None or n < max_jobs:
        if run_one(db, owner) is None:
            break
        n += 1
    return n


ORPHAN_AGE = timedelta(hours=1)


def reconcile(db: Session, *, apply: bool, now: datetime | None = None) -> list[str]:
    """Uploads that no batch names (the API stopped between writing the file and recording its batch), untouched for
    ORPHAN_AGE. A file being streamed is written to continuously, so its modification time keeps it safe. Returns the
    names; deletes them only with `apply`."""
    named = set(db.scalars(select(ContentImportBatch.file_key).where(ContentImportBatch.file_key.is_not(None))))
    db.rollback()
    cutoff = (now or datetime.now(UTC)).timestamp() - ORPHAN_AGE.total_seconds()
    orphans: list[str] = []
    for path in sorted(_root().iterdir()):
        if not path.is_file() or not path.name.endswith(".upload") or path.name in named:
            continue
        try:
            if path.stat().st_mtime > cutoff:
                continue
        except OSError:
            continue
        orphans.append(path.name)
        if apply:
            _remove(path.name)
    return orphans


@process_class("bulk")
def reconcile_main(argv: list[str] | None = None) -> int:
    """portal-import-reconcile [--apply]: list (or delete) import uploads that no batch names. Run hourly."""
    import argparse

    p = argparse.ArgumentParser(prog="portal-import-reconcile")
    p.add_argument("--apply", action="store_true", help="delete them (default: only list them)")
    args = p.parse_args(argv)
    if args.apply and (why := bulk_paused_now()):  # POOL-CAPS-01: the next hourly run does it
        print(f"skipped: {why}", flush=True)
        return 0
    with get_sessionmaker()() as db:
        orphans = reconcile(db, apply=args.apply)
    print(f"{len(orphans)} orphaned import upload(s){' deleted' if args.apply else ''}: {', '.join(orphans) or '-'}")
    return 0


@process_class("bulk")
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
            paused = bulk_pause_reason(db)  # POOL-CAPS-01: queued batches wait out a mock window
            n = 0 if paused else work(db, owner)
        if paused:
            print(f"paused: {paused}", flush=True)
        if n:
            print(f"handled {n} import batch(es)", flush=True)
        if args.once:
            return 0
        time.sleep(args.interval)
