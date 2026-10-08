"""Durable regrade jobs for rubric corrections (W06.S2.T3; PR #34 review W06-06).

An adjudicator's "apply" request only enqueues a :class:`RegradeJob` (one open job per correction; repeating the
request returns it). A separate worker process (``portal-written-worker``) claims jobs with ``SKIP LOCKED`` and a lease,
processes one bounded batch per claim (one short transaction per script) and records progress, failures and the final
state. A crashed worker's lease expires and another worker resumes from the per-script checkpoints. Failed scripts are
recorded with their error and the job ends ``failed`` until an adjudicator retries it. No database transaction is held
across batches, and nothing waits on slow external work.

Every job names the adjudicator who requested it, and every regraded script's audit entry names the job and the
approving adjudicator, so the worker is never an untraceable path around the MFA-protected request.
"""

from __future__ import annotations

import os
import socket
import time
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func, select, text
from sqlalchemy.dialects.postgresql import UUID, insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base, get_sessionmaker
from portal_api.errors import Conflict, NotFound
from portal_api.modules.audit.models import record
from portal_api.modules.identity.deps import Principal
from portal_api.modules.written import adjudication

LEASE = timedelta(minutes=2)
STATUSES = ("queued", "running", "succeeded", "failed", "superseded")


class RegradeJob(Base):
    __tablename__ = "written_regrade_job"
    __table_args__ = (
        CheckConstraint(
            "status in ('queued','running','succeeded','failed','superseded')", name="written_regrade_job_status"
        ),
        Index(
            "uq_written_regrade_job_open",
            "adjudication_id",
            unique=True,
            postgresql_where=text("status in ('queued','running')"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    adjudication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("written_rubric_adjudication.id", ondelete="RESTRICT"), index=True
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="queued")
    processed: Mapped[int] = mapped_column(Integer, default=0)
    regraded: Mapped[int] = mapped_column(Integer, default=0)
    unaffected: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    remaining: Mapped[int | None] = mapped_column(Integer)
    batches: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    lease_owner: Mapped[str | None] = mapped_column(String(120))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _now(db: Session) -> datetime:
    now: datetime = db.execute(select(func.clock_timestamp())).scalar_one()
    return now


def enqueue(db: Session, adj_id: uuid.UUID, requested_by: uuid.UUID, reason: str) -> RegradeJob:
    """Queue the correction's regrade, or return the job already open for it. The caller commits."""
    db.execute(
        insert(RegradeJob)
        .values(id=uuid.uuid4(), adjudication_id=adj_id, requested_by=requested_by, reason=reason[:500])
        .on_conflict_do_nothing(index_elements=["adjudication_id"], index_where=text("status in ('queued','running')"))
    )
    job = db.scalar(
        select(RegradeJob).where(RegradeJob.adjudication_id == adj_id, RegradeJob.status.in_(("queued", "running")))
    )
    assert job is not None
    record(
        db,
        actor=requested_by,
        action="written.regrade_enqueued",
        target_type="written_rubric_adjudication",
        target_id=str(adj_id),
        details={"job": str(job.id), "reason": reason[:200]},
    )
    return job


def request_run(db: Session, who: Principal, adj_id: uuid.UUID) -> RegradeJob:
    """An MFA adjudicator in scope asks for the correction to be applied (W06-01/06)."""
    adj = db.get(adjudication.RubricAdjudication, adj_id)
    if adj is None:
        raise NotFound("Correction not found.")
    adjudication.require_adjudicator(db, who, adj.grade_number, adj.subject_code)
    if adj.status != "active":
        raise Conflict("This correction was superseded; apply the one that replaced it.", code_reason="SUPERSEDED")
    job = enqueue(db, adj.id, who.user.id, "applied by an adjudicator")
    db.commit()
    db.refresh(job)
    return job


def get(db: Session, who: Principal, job_id: uuid.UUID) -> RegradeJob:
    job = db.get(RegradeJob, job_id)
    if job is None:
        raise NotFound("Job not found.")
    adjudication.get(db, who, job.adjudication_id)  # same read scope as the correction
    return job


def retry(db: Session, who: Principal, job_id: uuid.UUID) -> RegradeJob:
    """Re-queue a failed job: its failed scripts become eligible again (their earlier errors stay in the audit)."""
    job = db.scalar(select(RegradeJob).where(RegradeJob.id == job_id).with_for_update())
    if job is None:
        raise NotFound("Job not found.")
    adj = db.get(adjudication.RubricAdjudication, job.adjudication_id)
    assert adj is not None
    adjudication.require_adjudicator(db, who, adj.grade_number, adj.subject_code)
    if job.status != "failed":
        raise Conflict("Only a failed job can be retried.", code_reason="NOT_FAILED")
    if db.scalar(
        select(RegradeJob.id).where(
            RegradeJob.adjudication_id == job.adjudication_id, RegradeJob.status.in_(("queued", "running"))
        )
    ):
        raise Conflict("Another run of this correction is already queued.", code_reason="ALREADY_QUEUED")
    db.execute(
        text("delete from written_rubric_regrade where adjudication_id = :a and status = 'failed'"),
        {"a": str(job.adjudication_id)},
    )
    job.status, job.failed, job.last_error, job.finished_at = "queued", 0, None, None
    job.updated_at = _now(db)
    record(
        db,
        actor=who.user.id,
        action="written.regrade_retried",
        target_type="written_rubric_adjudication",
        target_id=str(job.adjudication_id),
        details={"job": str(job.id)},
    )
    db.commit()
    db.refresh(job)
    return job


def _claim(db: Session, owner: str) -> RegradeJob | None:
    now = _now(db)
    job = db.scalar(
        select(RegradeJob)
        .where(
            (RegradeJob.status == "queued") | ((RegradeJob.status == "running") & (RegradeJob.lease_expires_at < now))
        )
        .order_by(RegradeJob.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        db.rollback()
        return None
    job.status = "running"
    job.lease_owner = owner
    job.lease_expires_at = now + LEASE
    job.started_at = job.started_at or now
    job.updated_at = now
    db.commit()
    return job


def run_one_batch(db: Session, owner: str, batch: int = 50) -> dict[str, Any] | None:
    """Claim one job and process one bounded batch of it. Returns what happened, or None when nothing is queued."""
    job = _claim(db, owner)
    if job is None:
        return None
    job_id, adj_id = job.id, job.adjudication_id
    out = adjudication.process_batch(db, adj_id, batch, job_id)
    job = db.scalar(select(RegradeJob).where(RegradeJob.id == job_id).with_for_update())
    assert job is not None
    now = _now(db)
    job.processed += out["processed"]
    job.regraded += out["regraded"]
    job.unaffected += out["unaffected"]
    job.failed += out["failed"]
    job.remaining = out["remaining"]
    job.batches += 1
    job.last_error = out["last_error"] or job.last_error
    job.updated_at = now
    job.lease_owner, job.lease_expires_at = None, None
    if out["superseded"]:
        job.status, job.finished_at = "superseded", now
    elif out["remaining"] == 0:
        job.status = "failed" if job.failed else "succeeded"
        job.finished_at = now
    else:
        job.status = "queued"  # more to do: back in the queue for the next claim (any worker)
    db.commit()
    return {"job": str(job_id), "status": job.status, **out}


def work(db: Session, batch: int = 50, max_batches: int | None = None, owner: str | None = None) -> int:
    """Drain the queue (tests, the CLI). Returns how many scripts were processed."""
    owner = owner or f"{socket.gethostname()}:{os.getpid()}"
    done = n = 0
    while max_batches is None or n < max_batches:
        out = run_one_batch(db, owner, batch)
        if out is None:
            break
        done += out["processed"] + out["failed"]
        n += 1
    return done


def worker_main(argv: list[str] | None = None) -> int:
    """portal-written-worker [--once] [--batch N] [--interval S]: the written regrade worker process."""
    import argparse

    p = argparse.ArgumentParser(prog="portal-written-worker")
    p.add_argument("--once", action="store_true", help="drain the queue once and exit")
    p.add_argument("--batch", type=int, default=50)
    p.add_argument("--interval", type=float, default=2.0)
    args = p.parse_args(argv)
    owner = f"{socket.gethostname()}:{os.getpid()}"
    print(f"written worker {owner} started", flush=True)
    while True:
        with get_sessionmaker()() as db:  # a fresh session per drain: no connection kept across idle waits
            n = work(db, args.batch, owner=owner)
        if n:
            print(f"processed {n} script(s)", flush=True)
        if args.once:
            return 0
        time.sleep(args.interval)
