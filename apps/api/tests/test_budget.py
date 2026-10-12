"""P01.S4.T4 (BUDGET-01): the §5.8 connection budget is data, and it adds up. Core 245 plus written 24 is 269
planned connections; every installed database command belongs to a budgeted class, so no process runs unbudgeted;
the peak, including rolling-deploy overlap, is checked against the funded capacity when it is known (B03), and the
release manifest records the plan. Planning numbers only: measurement belongs to P20."""

from __future__ import annotations

import tomllib
from pathlib import Path

from portal_api import budget, release


def test_the_plan_matches_section_5_8() -> None:
    t = budget.totals()
    assert (t["core"], t["written"], t["planned"]) == (245, 24, 269)
    assert t["peak"] == 269 + budget.DEPLOY_OVERLAP_API_REPLICAS * 10  # overlap is budgeted, not forgotten


def test_every_database_command_is_budgeted() -> None:
    project = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf8"))
    scripts = set(project["project"]["scripts"])
    accounted = set(budget.ENTRY_POINTS) | set(budget.DEVELOPMENT_ONLY) | set(budget.NO_DATABASE)
    assert scripts - accounted == set(), "a new command needs a budget class (portal_api/budget.py)"
    assert accounted - scripts == set(), "the budget names a command that no longer exists"
    assert budget.check(None) == []


def test_the_peak_must_fit_the_funded_capacity() -> None:
    peak = budget.totals()["peak"]
    assert budget.check(peak) == []
    assert any("exceeds the funded" in p for p in budget.check(peak - 1))
    assert release.manifest()["connection_budget"] == budget.totals()
