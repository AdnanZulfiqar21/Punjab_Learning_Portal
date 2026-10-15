"""The §5.8 connection and background-work budget as data (roadmap P01.S4.T4; BUDGET-01).

Every process that opens database connections belongs to one budgeted class with a process count and a per-process
pool; the total is what the database (or its pooler) must actually admit at peak, including deployment overlap and
reserves. A per-process pool is multiplied by its process count, never mislabelled as per replica. Production refuses
pool overflow (config validator), so a pool size is a hard ceiling.

**Enforced per process (P17.S2.T2, POOL-CAPS-01):** every installed command declares its class with `process_class`,
which caps that process's database pool at the class's per-process connections before the first connection is
opened, and a test checks that every command in `ENTRY_POINTS` does. **Bulk work pauses in mock windows:** bulk-class
commands claim no new work from `BULK_PAUSE_MARGIN` before a scheduled mock window opens until the same margin after
it closes (`bulk_pause_reason`), unless `PORTAL_BULK_PAUSE_IN_MOCK_WINDOWS=false`. CPU and memory caps belong to the
deployment (B03).

These are **planning numbers** from the roadmap, not measurements: the funded server/pooler limit, autoscaling maxima
and the measured envelopes come with hosting (B03) and the load qualification (P20, AC50/AC63). `portal-budget`
prints the sheet and, given the funded capacity (`PORTAL_DB_SERVER_CONNECTIONS`), says whether the plan fits.
"""

from __future__ import annotations

import functools
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

F = TypeVar("F", bound=Callable[..., Any])


@dataclass(frozen=True)
class Pool:
    name: str
    processes: int
    connections_each: int
    note: str
    written: bool = False

    @property
    def total(self) -> int:
        return self.processes * self.connections_each


# §5.8 core planning budget (245) and the proposed written addition (24): 269 at peak.
PLAN: tuple[Pool, ...] = (
    Pool("api", 20, 10, "single-process API replicas; request work runs in a bounded threadpool"),
    Pool("critical", 4, 5, "score finalisation, submission receipts, entitlement grants, essential notifications"),
    Pool("standard", 4, 3, "reminders, analytics, indexing"),
    Pool("bulk", 2, 3, "imports, exports, media, OCR, reports, AI drafting; paused in mock windows when needed"),
    Pool("reserve", 1, 7, "migrations, administration, monitoring"),
    Pool("written.ingestion", 2, 3, "script upload validation and previews", written=True),
    Pool("written.reading", 4, 2, "reading and deadline jobs", written=True),
    Pool("written.assessment", 4, 2, "automatic assessment (disabled until B10)", written=True),
    Pool("written.regrade", 1, 2, "rubric corrections and regrades", written=True),
)

# Every installed command that touches the database, by budget class. Development fixtures are never deployed.
ENTRY_POINTS: dict[str, str] = {
    "portal-expire-attempts": "critical",
    "portal-mcq-regrade": "critical",
    "portal-notification-worker": "critical",
    "portal-notification-trial-reminders": "standard",
    "portal-export-worker": "bulk",
    "portal-asset-retention": "bulk",
    "portal-upload-reconcile": "bulk",
    "portal-help-import": "bulk",
    "portal-import-worker": "bulk",  # IMPORT-BULK-01
    "portal-import-reconcile": "bulk",  # OCT14 review: orphaned uploads
    "portal-import-catalogue": "reserve",
    "portal-grant-role": "reserve",
    "portal-written-previews": "written.ingestion",
    "portal-written-sweep-orphans": "written.ingestion",
    "portal-written-learner-deadlines": "written.reading",
    "portal-written-repair": "written.reading",
    "portal-written-auto-worker": "written.assessment",
    "portal-written-worker": "written.regrade",
}
DEVELOPMENT_ONLY = ("portal-dev-seed-staff", "portal-dev-seed-practice", "portal-dev-fixture-rubric-correction")
NO_DATABASE = ("portal-budget",)

BULK_PAUSE_MARGIN = timedelta(minutes=15)


def process_class(name: str) -> Callable[[F], F]:
    """Declare the budget class of an installed command (POOL-CAPS-01). Before the command runs, its process's database
    pool is capped at the class's per-process connections. A process that already has its pool (a test calling the
    function directly) keeps it: the cap is for the deployed process, which starts fresh."""
    pool = next((p for p in PLAN if p.name == name), None)
    if pool is None:
        raise ValueError(f"{name} is not a budgeted class")

    def wrap(fn: F) -> F:
        @functools.wraps(fn)
        def run(*args: Any, **kwargs: Any) -> Any:
            from portal_api import db

            db.cap_pool(pool.connections_each)
            return fn(*args, **kwargs)

        run.budget_class = name  # type: ignore[attr-defined]
        return run  # type: ignore[return-value]

    return wrap


def bulk_pause_reason(db: Session) -> str | None:
    """Why bulk work must wait now (P17.S2.T2), or None: a scheduled mock window is open or about to open."""
    from sqlalchemy import func, select

    from portal_api.config import get_settings
    from portal_api.modules.assessment.sessions import MockSession

    if not get_settings().bulk_pause_in_mock_windows:
        return None
    now = db.execute(select(func.now())).scalar_one()
    session = db.scalar(
        select(MockSession)
        .where(
            MockSession.status == "scheduled",
            MockSession.starts_at - BULK_PAUSE_MARGIN <= now,
            MockSession.window_closes_at + BULK_PAUSE_MARGIN >= now,
        )
        .order_by(MockSession.starts_at)
        .limit(1)
    )
    if session is None:
        return None
    margin = int(BULK_PAUSE_MARGIN.total_seconds() // 60)
    until = f"{session.window_closes_at:%Y-%m-%d %H:%M} UTC + {margin} min"
    return f"bulk work is paused for the scheduled mock window '{session.title}' (until {until})"


def bulk_paused_now() -> str | None:
    """`bulk_pause_reason` in a short session of its own, for commands that run once."""
    from portal_api.db import get_sessionmaker

    with get_sessionmaker()() as db:
        return bulk_pause_reason(db)


# A rolling deployment briefly runs old and new API replicas side by side; budget that overlap explicitly.
DEPLOY_OVERLAP_API_REPLICAS = 2


def totals(plan: tuple[Pool, ...] = PLAN) -> dict[str, int]:
    core = sum(p.total for p in plan if not p.written)
    written = sum(p.total for p in plan if p.written)
    api = next(p for p in plan if p.name == "api")
    overlap = DEPLOY_OVERLAP_API_REPLICAS * api.connections_each
    return {
        "core": core,
        "written": written,
        "planned": core + written,
        "overlap": overlap,
        "peak": core + written + overlap,
    }


def check(server_connections: int | None, plan: tuple[Pool, ...] = PLAN) -> list[str]:
    """Problems with the plan; with the funded capacity, whether the peak (including overlap) fits it."""
    problems = []
    names = {p.name for p in plan}
    for command, cls in ENTRY_POINTS.items():
        if cls not in names:
            problems.append(f"{command} is assigned to {cls}, which has no budgeted pool")
    if server_connections is not None:
        peak = totals(plan)["peak"]
        if peak > server_connections:
            problems.append(f"the planned peak of {peak} connections exceeds the funded {server_connections}")
    return problems


def sheet(plan: tuple[Pool, ...] = PLAN) -> str:
    rows = [f"{'class':<20}{'processes':>10}{'each':>6}{'total':>7}  note"]
    rows += [f"{p.name:<20}{p.processes:>10}{p.connections_each:>6}{p.total:>7}  {p.note}" for p in plan]
    t = totals(plan)
    rows.append(
        f"core {t['core']} + written {t['written']} = {t['planned']}; rolling-deploy overlap +{t['overlap']}; "
        f"peak {t['peak']}"
    )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    raw = os.environ.get("PORTAL_DB_SERVER_CONNECTIONS")
    capacity = int(raw) if raw else None
    sys.stdout.write(sheet() + "\n")
    problems = check(capacity)
    for p in problems:
        sys.stdout.write(f"PROBLEM: {p}\n")
    if capacity is None:
        sys.stdout.write("No funded capacity given (PORTAL_DB_SERVER_CONNECTIONS); fit not checked (B03).\n")
    return 1 if problems else 0
