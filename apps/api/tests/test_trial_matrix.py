"""P14.S8.T3 (TRIAL-MATRIX-01): the trial acceptance matrix stays complete and honest.

Every trial scenario (AC29-AC44, AC55, AC64-AC66) has a row. Every cited test exists. A scenario that needs
real-device or payment-sandbox evidence is never marked Met: fixture verdicts can't prove real device recall, and
no payment provider is integrated yet.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MATRIX = ROOT / "docs" / "project" / "TRIAL_ACCEPTANCE_MATRIX.md"
TESTS = Path(__file__).resolve().parent
E2E = ROOT / "apps" / "web" / "e2e"
REQUIRED = {f"AC{n}" for n in [*range(29, 45), 55, 64, 65, 66]}
STATUSES = {"Met", "Protocol tested", "Blocked"}
EXTERNAL = ("real device", "payment sandbox")


def _rows() -> dict[str, list[str]]:
    rows = {}
    for line in MATRIX.read_text(encoding="utf-8").splitlines():
        if re.match(r"^\| AC\d+ \|", line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            assert len(cells) == 6, line
            rows[cells[0]] = cells
    return rows


def _test_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {n.name for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")}


def test_every_trial_scenario_has_one_row_with_a_known_status() -> None:
    rows = _rows()
    assert set(rows) == REQUIRED
    for ac, (_, _, evidence, _, status, limits) in rows.items():
        assert status in STATUSES, (ac, status)
        assert limits, ac  # blockers and detection limits are always stated, even as "none"
        if any(kind in evidence for kind in EXTERNAL):
            assert status != "Met", f"{ac} needs {evidence} evidence and can't be Met from API tests"


def test_every_cited_test_exists() -> None:
    for ac, cells in _rows().items():
        for module, name in re.findall(r"`(test_[a-z0-9_]+\.py)::(test_[a-z0-9_]+)`", cells[3]):
            path = TESTS / module
            assert path.exists(), (ac, module)
            assert name in _test_names(path), (ac, module, name)
        for spec in re.findall(r"e2e `([a-z0-9-]+\.spec\.ts)`", cells[3]):
            assert (E2E / spec).exists(), (ac, spec)
