"""The §5.8 connection and background-work budget as data (roadmap P01.S4.T4; BUDGET-01).

Every process that opens database connections belongs to one budgeted class with a process count and a per-process
pool; the total is what the database (or its pooler) must actually admit at peak, including deployment overlap and
reserves. A per-process pool is multiplied by its process count, never mislabelled as per replica. Production refuses
pool overflow (config validator), so a pool size is a hard ceiling.

These are **planning numbers** from the roadmap, not measurements: the funded server/pooler limit, autoscaling maxima
and the measured envelopes come with hosting (B03) and the load qualification (P20, AC50/AC63). `portal-budget`
prints the sheet and, given the funded capacity (`PORTAL_DB_SERVER_CONNECTIONS`), says whether the plan fits.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass


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
