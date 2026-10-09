"""Asynchronous reporting exports (roadmap P16.S4.T2; EXPORTS-01).

A request only enqueues an :class:`ExportJob` owned by the requester. A separate bulk worker (``portal-export-worker``)
claims queued jobs with ``SKIP LOCKED`` and a lease, generates the file into private storage (never a public path) and
records the outcome. Nothing slow runs inside a web request.

* **Kinds** (`KINDS`): each names the permission it needs, its format and a generator. `audit_events` (redacted audit
  trail, CSV, `view_audit`) and `personal_data` (the requester's own data, JSON, any signed-in person).
* **Permission** is checked at request, again by the worker before generating, and again at download, so a role
  removed in the meantime stops the download. Jobs are visible only to their owner (404 for anyone else).
* **Result release (OCT9-01):** `personal_data` uses the same release policy as every other learner surface at
  generation, and records which attempts' scores it contains. At download, if any of them is held again (staff moved a
  release later), the file is withdrawn and the job expires; the person can request a fresh export.
* **Bounded:** at most `MAX_ROWS` rows (else the job fails with a "narrow the filter" reason); at most
  `MAX_OPEN_PER_USER` open jobs per person.
* **Lifecycle:** queued → running → ready | failed | cancelled; ready → expired after `TTL` (the worker deletes the
  file). A failed job can be retried up to `MAX_TRIES`; a queued or running job can be cancelled (a running worker
  discards its output). A crashed worker's lease expires and another worker takes the job.
* **Downloads** are counted and audited (`export.downloaded`). CSV cells are neutralised against formula injection.
"""

from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import os
import socket
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base, get_sessionmaker
from portal_api.errors import Conflict, Forbidden, NotFound, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.identity.deps import Principal
from portal_api.modules.identity.permissions import Permission

LEASE = timedelta(minutes=5)
TTL = timedelta(hours=24)
MAX_ROWS = 100_000
MAX_OPEN_PER_USER = 3
MAX_TRIES = 3
OPEN = ("queued", "running")


class ExportJob(Base):
    __tablename__ = "export_job"
    __table_args__ = (
        CheckConstraint(
            "status in ('queued','running','ready','failed','cancelled','expired')", name="export_job_status"
        ),
        Index("ix_export_job_queue", "status", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="RESTRICT"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(10), default="queued")
    tries: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    row_count: Mapped[int | None] = mapped_column(Integer)
    byte_size: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64))
    file_key: Mapped[str | None] = mapped_column(String(120))  # private storage name; never shown to anyone
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # what the file contains (e.g. attempt IDs)
    downloads: Mapped[int] = mapped_column(Integer, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(120))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ------------------------------------------------------------------ kinds
class TooLarge(Exception):
    pass


@dataclass(frozen=True)
class Kind:
    permission: Permission | None  # None: any signed-in person, for their own data only
    media_type: str
    extension: str
    generate: Callable[
        [Session, Principal, dict[str, Any]], tuple[bytes, int | None, dict[str, Any]]
    ]  # rows: None if not a table
    params: Callable[[dict[str, Any]], dict[str, Any]]


def csv_safe(value: object) -> str:
    """Neutralise a cell a spreadsheet would run as a formula."""
    from portal_api.modules.content.imports import csv_safe as _safe

    return _safe(value)


def _audit_params(p: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in ("action", "target_type"):
        v = p.get(k)
        if v is not None:
            if not isinstance(v, str) or not 1 <= len(v) <= 80:
                raise Unprocessable(f"`{k}` must be text of at most 80 characters.")
            out[k] = v
    for k in ("since", "until"):
        v = p.get(k)
        if v is not None:
            try:
                out[k] = datetime.fromisoformat(str(v)).isoformat()
            except ValueError:
                raise Unprocessable(f"`{k}` must be an ISO date-time.") from None
    if "since" not in out:
        raise Unprocessable("Choose a start date (`since`) so the export stays bounded.")
    return out


def _audit_events(db: Session, who: Principal, p: dict[str, Any]) -> tuple[bytes, int | None, dict[str, Any]]:
    from portal_api.modules.audit.models import AuditEvent
    from portal_api.modules.audit.router import redact
    from portal_api.modules.identity.models import AppUser

    q = select(AuditEvent, AppUser.email).outerjoin(AppUser, AppUser.id == AuditEvent.actor_user_id)
    action = p.get("action")
    if action:
        q = q.where(AuditEvent.action.startswith(action) if action.endswith(".") else AuditEvent.action == action)
    if p.get("target_type"):
        q = q.where(AuditEvent.target_type == p["target_type"])
    q = q.where(AuditEvent.at >= datetime.fromisoformat(p["since"]))
    if p.get("until"):
        q = q.where(AuditEvent.at < datetime.fromisoformat(p["until"]))
    rows = db.execute(q.order_by(AuditEvent.at, AuditEvent.id).limit(MAX_ROWS + 1)).all()
    if len(rows) > MAX_ROWS:
        raise TooLarge
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["at", "action", "actor", "target_type", "target_id", "details", "correlation_id"])
    for e, email in rows:
        w.writerow(
            [
                csv_safe(e.at.isoformat()),
                csv_safe(e.action),
                csv_safe(email),
                csv_safe(e.target_type),
                csv_safe(e.target_id),
                csv_safe(json.dumps(redact(e.details or {}), ensure_ascii=False, sort_keys=True)),
                csv_safe(e.correlation_id),
            ]
        )
    return buf.getvalue().encode("utf-8"), len(rows), {}


def _personal_data(db: Session, who: Principal, p: dict[str, Any]) -> tuple[bytes, int | None, dict[str, Any]]:
    from portal_api.modules.identity import privacy

    body, _ = privacy.export(db, who.user)
    data = json.loads(body)
    scored = sorted({str(s["attempt_id"]) for s in data["practice"]["scores"]})
    return body, None, {"scored_attempts": scored}  # a document, not a table: no row count


def _no_params(p: dict[str, Any]) -> dict[str, Any]:
    if p:
        raise Unprocessable("This export takes no options.")
    return {}


KINDS: dict[str, Kind] = {
    "audit_events": Kind(Permission.view_audit, "text/csv; charset=utf-8", "csv", _audit_events, _audit_params),
    "personal_data": Kind(None, "application/json", "json", _personal_data, _no_params),
}


def _kind(name: str) -> Kind:
    k = KINDS.get(name)
    if k is None:
        raise Unprocessable("Unknown export.", choices=sorted(KINDS))
    return k


def _authorise(who: Principal, kind: Kind, *, interactive: bool = True) -> None:
    """Role check everywhere; MFA too for interactive requests where the permission matrix needs it."""
    from portal_api.modules.identity.permissions import MFA_REQUIRED

    if kind.permission is None:
        return
    if kind.permission not in who.permissions:
        raise Forbidden("You don't have permission for this export.")
    if interactive and kind.permission in MFA_REQUIRED and not who.claims.mfa:
        raise Forbidden("This export needs a multi-factor authenticated session. Sign in again with MFA.")


# ------------------------------------------------------------------ storage
def _root() -> Path:
    from portal_api.config import get_settings

    base = Path(os.environ.get("PORTAL_EXPORT_DIR") or Path(get_settings().evidence_dir).parent / "exports")
    if not base.is_absolute():
        base = Path(__file__).resolve().parents[4] / base
    base.mkdir(parents=True, exist_ok=True)
    return base


def _path(key: str) -> Path:
    return _root() / key


def _delete_file(job: ExportJob) -> None:
    if job.file_key:
        with contextlib.suppress(OSError):  # a file already gone is fine; the job still records expiry
            _path(job.file_key).unlink(missing_ok=True)
        job.file_key = None


# ------------------------------------------------------------------ requests
def _now(db: Session) -> datetime:
    now: datetime = db.execute(select(func.clock_timestamp())).scalar_one()
    return now


def request(db: Session, who: Principal, kind_name: str, params: dict[str, Any]) -> ExportJob:
    kind = _kind(kind_name)
    _authorise(who, kind)
    clean = kind.params(params or {})
    db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(f"export:{who.user.id}", 0))))
    open_jobs = db.scalar(
        select(func.count(ExportJob.id)).where(ExportJob.owner_id == who.user.id, ExportJob.status.in_(OPEN))
    )
    if (open_jobs or 0) >= MAX_OPEN_PER_USER:
        raise Conflict("You already have exports in progress. Wait for one to finish.", code_reason="TOO_MANY_OPEN")
    job = ExportJob(id=uuid.uuid4(), owner_id=who.user.id, kind=kind_name, params=clean, status="queued")
    db.add(job)
    record(db, actor=who.user.id, action="export.requested", target_type="export_job", target_id=str(job.id),
           details={"kind": kind_name, "params": clean})  # fmt: skip
    db.commit()
    db.refresh(job)
    return job


def own(db: Session, who: Principal, job_id: uuid.UUID, *, lock: bool = False) -> ExportJob:
    q = select(ExportJob).where(ExportJob.id == job_id)
    job = db.scalar(q.with_for_update() if lock else q)
    if job is None or job.owner_id != who.user.id:
        raise NotFound("Export not found.")  # never reveal another person's job
    return job


def mine(db: Session, who: Principal) -> list[ExportJob]:
    return list(
        db.scalars(
            select(ExportJob).where(ExportJob.owner_id == who.user.id).order_by(ExportJob.created_at.desc()).limit(50)
        )
    )


def cancel(db: Session, who: Principal, job_id: uuid.UUID) -> ExportJob:
    job = own(db, who, job_id, lock=True)
    if job.status not in OPEN:
        raise Conflict("Only a queued or running export can be cancelled.", code_reason="NOT_OPEN")
    job.status, job.finished_at, job.lease_owner, job.lease_expires_at = "cancelled", _now(db), None, None
    record(
        db, actor=who.user.id, action="export.cancelled", target_type="export_job", target_id=str(job.id), details={}
    )
    db.commit()
    return job


def retry(db: Session, who: Principal, job_id: uuid.UUID) -> ExportJob:
    job = own(db, who, job_id, lock=True)
    _authorise(who, _kind(job.kind))
    if job.status != "failed":
        raise Conflict("Only a failed export can be retried.", code_reason="NOT_FAILED")
    if job.tries >= MAX_TRIES:
        raise Conflict("This export failed too many times. Request a new one.", code_reason="TOO_MANY_TRIES")
    job.status, job.error, job.finished_at = "queued", None, None
    record(db, actor=who.user.id, action="export.retried", target_type="export_job", target_id=str(job.id), details={})
    db.commit()
    return job


def download(db: Session, who: Principal, job_id: uuid.UUID) -> tuple[bytes, str, str]:
    """The file, its media type and a download name; permission and result release are rechecked now."""
    job = own(db, who, job_id, lock=True)
    kind = _kind(job.kind)
    _authorise(who, kind)
    now = _now(db)
    if job.status == "ready" and job.expires_at is not None and job.expires_at <= now:
        _expire(job, "expired")
    if job.status == "ready" and job.kind == "personal_data" and _release_changed(db, job):
        _expire(job, "A result in this export is no longer released. Request a new export.")
        record(db, actor=who.user.id, action="export.withdrawn", target_type="export_job", target_id=str(job.id),
               details={"reason": "result release moved later"})  # fmt: skip
        db.commit()
        raise Conflict("A result in this export is no longer released. Request a new export.", code_reason="WITHDRAWN")
    if job.status != "ready" or job.file_key is None:
        db.commit()
        raise Conflict("This export isn't ready to download.", code_reason="NOT_READY", status=job.status)
    data = _path(job.file_key).read_bytes()
    if hashlib.sha256(data).hexdigest() != job.sha256:
        raise Conflict("This export's file is damaged. Request a new one.", code_reason="DAMAGED")
    job.downloads += 1
    record(db, actor=who.user.id, action="export.downloaded", target_type="export_job", target_id=str(job.id),
           details={"kind": job.kind, "download": job.downloads})  # fmt: skip
    db.commit()
    stamp = (job.finished_at or now).strftime("%Y%m%d-%H%M")
    return data, kind.media_type, f"portal-{job.kind.replace('_', '-')}-{stamp}.{kind.extension}"


def _expire(job: ExportJob, reason: str) -> None:
    _delete_file(job)
    job.status = "expired"
    if reason != "expired":
        job.error = reason


def _release_changed(db: Session, job: ExportJob) -> bool:
    from portal_api.modules.assessment.models import Attempt
    from portal_api.modules.assessment.sessions import held_forms

    scored = [uuid.UUID(a) for a in (job.content or {}).get("scored_attempts", [])]
    if not scored:
        return False
    held = held_forms(db, job.owner_id)
    if not held:
        return False
    forms = set(db.scalars(select(Attempt.form_id).where(Attempt.id.in_(scored))))
    return bool(forms & set(held))


# ------------------------------------------------------------------ worker
def _principal(db: Session, user_id: uuid.UUID) -> Principal | None:
    """The requester's *current* roles, for the worker's recheck (no session, so no MFA claim)."""
    from portal_api.modules.identity.models import AppUser, StaffRoleGrant
    from portal_api.modules.identity.permissions import Role, permissions_for
    from portal_api.modules.identity.tokens import Claims

    user = db.get(AppUser, user_id)
    if user is None or user.status != "active":
        return None
    grants = db.scalars(
        select(StaffRoleGrant.role).where(StaffRoleGrant.user_id == user.id, StaffRoleGrant.revoked_at.is_(None))
    ).all()
    roles = frozenset(Role(r) for r in grants)
    claims = Claims(issuer=user.issuer, subject=user.subject, email=user.email, token_id=None, expires_at=0, mfa=False)
    return Principal(user=user, claims=claims, roles=roles, permissions=permissions_for(set(roles)))


def run_once(db: Session, worker: str | None = None) -> ExportJob | None:
    """Claim one job, generate it, record the outcome. Returns the job handled, if any."""
    worker = worker or f"{socket.gethostname()}:{os.getpid()}"
    now = _now(db)
    sweep(db, now)
    job = db.scalar(
        select(ExportJob)
        .where(
            (ExportJob.status == "queued")
            | ((ExportJob.status == "running") & (ExportJob.lease_expires_at < now))  # a crashed worker's job
        )
        .order_by(ExportJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        db.rollback()
        return None
    job.status, job.lease_owner, job.lease_expires_at = "running", worker, now + LEASE
    job.started_at, job.tries = now, job.tries + 1
    db.commit()
    job_id, owner, kind_name, params = job.id, job.owner_id, job.kind, dict(job.params)

    error: str | None = None
    try:
        who = _principal(db, owner)
        kind = _kind(kind_name)
        if who is None:
            raise Forbidden("The account that requested this export is no longer active.")
        _authorise(who, kind, interactive=False)  # the role is rechecked by the worker
        body, rows, content = kind.generate(db, who, params)
        db.rollback()  # the generator only read
    except TooLarge:
        error = f"More than {MAX_ROWS:,} rows. Narrow the filter and request again."
    except (Forbidden, Unprocessable) as e:
        error = e.detail
    except Exception as e:
        error = f"Export failed: {type(e).__name__}."
    job = db.scalar(select(ExportJob).where(ExportJob.id == job_id).with_for_update())
    assert job is not None
    if job.status != "running" or job.lease_owner != worker:
        db.rollback()  # cancelled, or another worker took over after our lease ran out: discard
        return job
    done = _now(db)
    job.lease_owner, job.lease_expires_at, job.finished_at = None, None, done
    if error is not None:
        job.status, job.error = "failed", error
        record(db, actor=None, action="export.failed", target_type="export_job", target_id=str(job.id),
               details={"kind": job.kind, "error": error, "try": job.tries})  # fmt: skip
    else:
        key = f"{job.id}.{_kind(job.kind).extension}"
        tmp = _path(key + ".part")
        tmp.write_bytes(body)
        tmp.replace(_path(key))
        job.status, job.file_key, job.row_count = "ready", key, rows
        job.byte_size, job.sha256, job.content = len(body), hashlib.sha256(body).hexdigest(), content
        job.expires_at = done + TTL
        record(db, actor=None, action="export.ready", target_type="export_job", target_id=str(job.id),
               details={"kind": job.kind, "rows": rows, "bytes": len(body)})  # fmt: skip
    db.commit()
    return job


def sweep(db: Session, now: datetime) -> int:
    """Expire ready exports past their time and delete their files."""
    jobs = list(
        db.scalars(
            select(ExportJob)
            .where(ExportJob.status == "ready", ExportJob.expires_at <= now)
            .with_for_update(skip_locked=True)
            .limit(100)
        )
    )
    for j in jobs:
        _expire(j, "expired")
    if jobs:
        db.commit()
    return len(jobs)


def worker_main() -> None:  # pragma: no cover - long-running process
    idle = float(os.environ.get("PORTAL_EXPORT_IDLE_SECONDS", "5"))
    factory = get_sessionmaker()
    while True:
        with factory() as db:
            handled = run_once(db)
        if handled is None:
            time.sleep(idle)
