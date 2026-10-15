"""The written workload guard (roadmap W09.S1.T3, §20.11.1 "MCQ-health protection", WA-AC68; WORKLOAD-GUARD-01).

Written work must never slow down MCQ exams. When MCQ saves or the database are under strain, the guard pauses new
expensive written work and recovers slowly.

**Health inputs.** Every API process publishes a `HealthSample` every `health_sample_s` seconds (20 by default): its
durable MCQ saves (save and submit) in that window, how many took longer than the save budget (§6.2b: p95 ≤ 1 s),
how many failed with 5xx, and its pool use. A check reads the samples of the last minute from every process, plus:

* the database's own connection use (`pg_stat_activity` against `max_connections`), which trips the guard at once;
* finalised MCQ submissions still waiting for a score (an explicit queue signal, for sparse traffic).

A rule only counts when it has enough evidence: slow saves need at least `MIN_SAVES` saves in the minute (a p95 of
five saves means nothing); save errors need at least `MIN_ERRORS` failures.

**States and hysteresis.** `healthy` → `paused` on database saturation at once, or on any other fault in `TRIP_CHECKS`
consecutive checks (one check every `CHECK_S` seconds at most, whichever process runs it). `paused` → `recovering` only
after `HEALTHY_CHECKS` consecutive healthy checks *and* a `COOLDOWN` since the last fault; recovery then ramps work up
(`RAMP`: a quarter, then half, then all), and any fault sends it back to `paused`, restarting the cooldown. Every change
is audited with its reasons.

**What it pauses.** While paused: the written regrade and automatic-assessment workers claim no new work (work already
running finishes; neither holds a database connection while a provider thinks), new written tests can't be built or
started (503 `WRITTEN_PAUSED`, retry later), and bulk imports, exports and rebuilds wait (`budget.bulk_pause_reason`).
While recovering, the workers take only their ramp share per pass. Uploads, page previews, sealing and receipts of
tests already admitted are never paused: that capacity stays reserved for admitted work. Learners see that marking may
take longer.

All thresholds are proposed operating controls (§20.11.1), not measured ones: they are pinned in the deployment policy
once load evidence exists (W09.S2, B03).
"""

from __future__ import annotations

import logging
import os
import socket
import threading
import time
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import Depends
from sqlalchemy import CheckConstraint, DateTime, Float, Integer, String, Text, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api import observability
from portal_api.db import Base, get_session
from portal_api.errors import Unavailable
from portal_api.modules.audit.models import record

log = logging.getLogger("portal.guard")

State = Literal["healthy", "paused", "recovering"]
NAME = "written"
CHECK_S = 20  # at most one evaluation per this many seconds, across every process
WINDOW = timedelta(seconds=60)  # the rolling minute the save rules read
SAVE_BUDGET_MS = 1000.0  # §6.2b tap-to-durable-save p95
SLOW_SHARE = 0.05  # more than 5% of saves over budget = p95 over budget
MIN_SAVES = 30  # fewer saves than this in the minute: latency isn't judged
ERROR_RATIO = 0.01
MIN_ERRORS = 3
DB_SATURATION = 0.9  # share of max_connections in use: trips at once
SCORING_BACKLOG = 5  # MCQ submissions waiting over SCORING_WAIT for a score
SCORING_WAIT = timedelta(minutes=2)
TRIP_CHECKS = 3
HEALTHY_CHECKS = 3
COOLDOWN = timedelta(minutes=5)
RAMP = (25, 50)  # percent of normal work while recovering, one step per healthy check, then healthy
SAMPLE_RETENTION = timedelta(hours=1)
# Durable MCQ saves (§6.2b): answer operations and the final submission.
SAVE_ROUTES = frozenset({"/v1/attempts/{attempt_id}/answers", "/v1/attempts/{attempt_id}/submit"})


class WrittenPaused(Unavailable):
    """New written tests wait out a guard pause (503 with Retry-After); nothing was recorded as done."""

    code = "WRITTEN_PAUSED"
    retry_after = 120


class HealthSample(Base):
    """One API process's MCQ save health over one sample window."""

    __tablename__ = "health_sample"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    process: Mapped[str] = mapped_column(String(120))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    window_s: Mapped[float] = mapped_column(Float)
    saves: Mapped[int] = mapped_column(Integer)
    slow_saves: Mapped[int] = mapped_column(Integer)
    save_errors: Mapped[int] = mapped_column(Integer)
    pool_in_use: Mapped[int] = mapped_column(Integer)
    pool_size: Mapped[int] = mapped_column(Integer)


class WorkloadGuard(Base):
    """The guard's state, one row per guard, changed only under its row lock."""

    __tablename__ = "workload_guard"
    __table_args__ = (CheckConstraint("state in ('healthy','paused','recovering')", name="workload_guard_state"),)
    name: Mapped[str] = mapped_column(String(20), primary_key=True)
    state: Mapped[str] = mapped_column(String(10), default="healthy")
    ramp: Mapped[int] = mapped_column(Integer, default=100)  # percent of normal work allowed
    faults: Mapped[list[str]] = mapped_column(JSONB, default=list)  # the last check's fault reasons
    unhealthy_checks: Mapped[int] = mapped_column(Integer, default=0)
    healthy_checks: Mapped[int] = mapped_column(Integer, default=0)
    last_fault_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(Text, default="")


def _now(db: Session) -> datetime:
    now: datetime = db.execute(select(func.clock_timestamp())).scalar_one()
    return now


# ---------------------------------------------------------------- samples (API processes)
_PROCESS = f"{socket.gethostname()}:{os.getpid()}"
_last_sample = time.monotonic()


def publish_sample(db: Session, since: float | None = None) -> HealthSample:
    """Write this process's save health since its last sample (or `since`, a monotonic time). Commits."""
    global _last_sample
    from portal_api.db import get_engine

    start = _last_sample if since is None else since
    end = time.monotonic()
    saves = [e for e in observability.events_since(start) if e[1] in SAVE_ROUTES]
    pool = get_engine().pool
    sample = HealthSample(
        process=_PROCESS,
        window_end=_now(db),
        window_s=round(end - start, 3),
        saves=len(saves),
        slow_saves=sum(1 for e in saves if e[3] > SAVE_BUDGET_MS),
        save_errors=sum(1 for e in saves if e[2] >= 500),
        pool_in_use=int(getattr(pool, "checkedout", lambda: 0)()),
        pool_size=int(getattr(pool, "size", lambda: 0)()),
    )
    db.add(sample)
    db.execute(
        text("delete from health_sample where window_end < clock_timestamp() - make_interval(secs => :s)"),
        {"s": SAMPLE_RETENTION.total_seconds()},
    )
    db.commit()
    _last_sample = end
    return sample


def start_sampler(interval_s: float) -> threading.Thread | None:
    """In an API process: publish a sample and run a check every `interval_s` seconds (0 = off, as in tests)."""
    if interval_s <= 0:
        return None

    def loop() -> None:
        from portal_api.db import get_sessionmaker

        while True:
            time.sleep(interval_s)
            try:
                with get_sessionmaker()() as db:
                    publish_sample(db)
                    check(db)
            except Exception:  # never let the sampler take the API down; the next pass tries again
                log.exception("health sample failed")

    t = threading.Thread(target=loop, name="health-sampler", daemon=True)
    t.start()
    return t


# ---------------------------------------------------------------- evaluation
def _db_saturation(db: Session) -> float:
    used, limit = db.execute(
        text(
            "select count(*) filter (where state is distinct from 'idle'), current_setting('max_connections')::int "
            "from pg_stat_activity where backend_type = 'client backend'"
        )
    ).one()
    return float(used) / float(limit) if limit else 0.0


def _scoring_backlog(db: Session, now: datetime) -> int:
    from portal_api.modules.assessment.models import Attempt, ScoreVersion

    scored = select(ScoreVersion.id).where(ScoreVersion.attempt_id == Attempt.id).exists()
    return int(
        db.scalar(
            select(func.count())
            .select_from(Attempt)
            .where(
                Attempt.status == "finalised",
                Attempt.finalised_at < now - SCORING_WAIT,
                Attempt.finalised_at > now - timedelta(hours=1),
                ~scored,
            )
        )
        or 0
    )


def faults(db: Session, now: datetime) -> tuple[list[str], bool]:
    """The current fault reasons, and whether one of them trips the guard at once."""
    out: list[str] = []
    immediate = False
    saturation = _db_saturation(db)
    if saturation >= DB_SATURATION:
        out.append(f"database connections {saturation:.0%} in use")
        immediate = True
    saves, slow, errors = db.execute(
        select(
            func.coalesce(func.sum(HealthSample.saves), 0),
            func.coalesce(func.sum(HealthSample.slow_saves), 0),
            func.coalesce(func.sum(HealthSample.save_errors), 0),
        ).where(HealthSample.window_end > now - WINDOW)
    ).one()
    if saves >= MIN_SAVES and slow / saves > SLOW_SHARE:
        out.append(f"{slow} of {saves} MCQ saves in the last minute took over {SAVE_BUDGET_MS:.0f} ms")
    if errors >= MIN_ERRORS and saves and errors / saves >= ERROR_RATIO:
        out.append(f"{errors} of {saves} MCQ saves in the last minute failed")
    backlog = _scoring_backlog(db, now)
    if backlog >= SCORING_BACKLOG:
        out.append(f"{backlog} MCQ submissions are waiting for a score")
    return out, immediate


def _row(db: Session) -> WorkloadGuard:
    row = db.scalar(select(WorkloadGuard).where(WorkloadGuard.name == NAME).with_for_update())
    if row is None:
        db.execute(
            text(
                "insert into workload_guard (name, state, ramp, faults, unhealthy_checks, healthy_checks, reason) "
                "values (:n, 'healthy', 100, '[]'::jsonb, 0, 0, '') on conflict (name) do nothing"
            ),
            {"n": NAME},
        )
        row = db.scalar(select(WorkloadGuard).where(WorkloadGuard.name == NAME).with_for_update())
    assert row is not None
    return row


def _move(db: Session, row: WorkloadGuard, state: State, ramp: int, reason: str, now: datetime) -> None:
    before = row.state
    row.state, row.ramp, row.reason, row.changed_at = state, ramp, reason, now
    if before != state:
        record(
            db,
            actor=None,
            action=f"workload_guard.{state}",
            target_type="workload_guard",
            target_id=NAME,
            details={"from": before, "ramp": ramp, "reason": reason, "faults": list(row.faults)},
        )
        log.warning("workload guard %s -> %s: %s", before, state, reason)


def check(db: Session, *, force: bool = False) -> WorkloadGuard:
    """Evaluate the health inputs once (at most every CHECK_S seconds unless forced) and move the state. Commits."""
    now = _now(db)
    row = _row(db)
    if not force and row.checked_at is not None and now - row.checked_at < timedelta(seconds=CHECK_S):
        db.commit()
        return row
    found, immediate = faults(db, now)
    row.faults, row.checked_at = found, now
    if found:
        row.last_fault_at = now
        row.healthy_checks = 0
        row.unhealthy_checks += 1
        if row.state == "recovering" or immediate or row.unhealthy_checks >= TRIP_CHECKS:
            _move(db, row, "paused", 0, "; ".join(found), now)
    else:
        row.unhealthy_checks = 0
        row.healthy_checks += 1
        if row.state == "paused":
            cooled = row.last_fault_at is None or now - row.last_fault_at >= COOLDOWN
            if row.healthy_checks >= HEALTHY_CHECKS and cooled:
                _move(db, row, "recovering", RAMP[0], "healthy again; ramping up", now)
        elif row.state == "recovering":
            later = [r for r in RAMP if r > row.ramp]
            if later:
                _move(db, row, "recovering", later[0], "healthy again; ramping up", now)
            else:
                _move(db, row, "healthy", 100, "healthy", now)
    db.commit()
    return row


def current(db: Session) -> WorkloadGuard | None:
    """The state as last decided (no evaluation)."""
    return db.get(WorkloadGuard, NAME)


def allowance(db: Session) -> float:
    """The share of normal written work a worker may take now (0 while paused). Runs a check when one is due."""
    row = check(db)
    return 0.0 if row.state == "paused" else row.ramp / 100.0


def paused_reason(db: Session) -> str | None:
    row = current(db)
    return f"the workload guard is protecting exams ({row.reason})" if row and row.state != "healthy" else None


def require_open(db: Session) -> None:
    """New written tests wait while the guard is paused (recovery lets them through)."""
    row = current(db)
    if row is not None and row.state == "paused":
        raise WrittenPaused(
            "Written tests are paused for a few minutes to keep exams in progress running smoothly. Nothing you have "
            "saved is affected. Please try again shortly."
        )


def open_for_new_tests(db: Annotated[Session, Depends(get_session)]) -> None:
    """Route dependency: building a new written test waits out a guard pause."""
    require_open(db)


def learner_notice(db: Session) -> str | None:
    """What a learner is told about written marking while the guard isn't healthy."""
    row = current(db)
    if row is None or row.state == "healthy":
        return None
    if row.state == "paused":
        return (
            "New written tests are paused for a few minutes to protect exams in progress. Scripts already submitted "
            "are kept and will be marked, but marking may take longer than usual."
        )
    return "Written marking is catching up after a short pause, so it may take a little longer than usual."


def snapshot(db: Session) -> dict[str, Any]:
    row = current(db)
    if row is None:
        return {"state": "healthy", "ramp": 100, "faults": [], "reason": "", "changed_at": None, "checked_at": None}
    return {
        "state": row.state,
        "ramp": row.ramp,
        "faults": list(row.faults),
        "reason": row.reason,
        "changed_at": row.changed_at,
        "checked_at": row.checked_at,
    }
