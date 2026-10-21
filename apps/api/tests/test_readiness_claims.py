"""Readiness claims need evidence (roadmap §2.3; READINESS-01).

`docs/project/RELEASE_CHECKLIST.md` records three states: Platform Ready, Content Ready and Public Launch Ready.
This guard fails CI if a state is claimed (anything other than NOT_READY) while any of its own checklist items is
unticked, or while any blocker in `docs/project/BLOCKERS.md` is still BLOCKED_EXTERNAL or BLOCKED_DECISION. A
blocker note is never passing evidence.

SEVERITY-01 (P00.S3.T2, roadmap §7.2 and AC60) adds: no readiness claim while a P0 or P1 defect in
`docs/project/DEFECTS.md` is open; defect rows use known severities and statuses; gate rows in
`docs/project/IMPLEMENTATION_REGISTER.md` use only the §7.2 gate states; and a gate is never PASSED while its row names
an open blocker.
"""

from __future__ import annotations

import re
from pathlib import Path

DOCS = Path(__file__).resolve().parents[3] / "docs" / "project"
STATES = ("Platform Ready", "Content Ready", "Public Launch Ready")
GATE_STATES = {"NOT_READY", "BLOCKED_EXTERNAL", "BLOCKED_DECISION", "FAILED", "PASSED", "INVALIDATED"}
SEVERITIES = {"P0", "P1", "P2", "P3"}
DEFECT_STATUSES = {"OPEN", "FIXED", "WONT_FIX"}


def _sections(text: str) -> dict[str, tuple[str, list[str]]]:
    out: dict[str, tuple[str, list[str]]] = {}
    current: str | None = None
    for line in text.splitlines():
        m = re.match(r"^## (Platform Ready|Content Ready|Public Launch Ready)\b.*?:\s*([A-Z_]+)\s*$", line)
        if m:
            current = m.group(1)
            out[current] = (m.group(2), [])
        elif line.startswith("## "):
            current = None
        elif current and line.lstrip().startswith("- ["):
            out[current][1].append(line.strip())
    return out


def _open_blockers(text: str) -> list[str]:
    return [
        line.split("|")[1].strip()
        for line in text.splitlines()
        if line.startswith("| B") and re.search(r"\|\s*BLOCKED_(EXTERNAL|DECISION)", line)
    ]


def _defects(text: str) -> list[dict[str, str]]:
    rows = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("| ") and len(cells) == 7 and cells[0] not in ("ID", "") and not set(cells[0]) <= {"-"}:
            rows.append(
                dict(zip(("id", "severity", "title", "found", "owner", "status", "evidence"), cells, strict=True))
            )
    return rows


def _open_p0_p1(defects: list[dict[str, str]]) -> list[str]:
    return [d["id"] for d in defects if d["severity"] in ("P0", "P1") and d["status"] == "OPEN"]


def _gate_problems(register: str, open_blockers: list[str]) -> list[str]:
    problems = []
    for line in register.splitlines():
        m = re.match(r"^\| (W?G\d\d\S*) \| ([A-Z_]+) \|(.*)$", line)
        if not m:
            continue
        gate, state, rest = m.groups()
        if state not in GATE_STATES:
            problems.append(f"{gate}: '{state}' is not a §7.2 gate state")
        named = [b for b in open_blockers if re.search(rf"\b{b}\b", rest)]
        if state == "PASSED" and named:
            problems.append(f"{gate} is PASSED while it names open blockers {named}")
    return problems


def test_every_readiness_state_is_recorded() -> None:
    sections = _sections((DOCS / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8"))
    assert set(sections) == set(STATES)


def test_no_readiness_state_is_claimed_without_evidence() -> None:
    sections = _sections((DOCS / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8"))
    blockers = _open_blockers((DOCS / "BLOCKERS.md").read_text(encoding="utf-8"))
    defects = _open_p0_p1(_defects((DOCS / "DEFECTS.md").read_text(encoding="utf-8")))
    wrong = []
    for state, (status, items) in sections.items():
        if status == "NOT_READY":
            continue
        unticked = [i for i in items if i.startswith("- [ ]")]
        if unticked or blockers or defects:
            wrong.append(
                f"{state} is {status} with {len(unticked)} unticked items, open blockers {blockers} "
                f"and open P0/P1 defects {defects}"
            )
    assert wrong == []


def test_defect_rows_use_known_severities_and_statuses() -> None:
    rows = _defects((DOCS / "DEFECTS.md").read_text(encoding="utf-8"))
    bad = [r["id"] for r in rows if r["severity"] not in SEVERITIES or r["status"] not in DEFECT_STATUSES]
    assert bad == []


def test_gates_use_section_7_2_states_and_never_pass_on_a_blocker() -> None:
    register = (DOCS / "IMPLEMENTATION_REGISTER.md").read_text(encoding="utf-8")
    blockers = _open_blockers((DOCS / "BLOCKERS.md").read_text(encoding="utf-8"))
    assert _gate_problems(register, blockers) == []


def test_the_checks_catch_what_they_guard() -> None:
    header = "| ID | Severity | Title | Found | Owner | Status | Evidence |\n|---|---|---|---|---|---|---|\n"
    defects = _defects(header + "| D001 | P1 | Fixture: submit fails | 2026-10-21 | Eng | OPEN | none |\n")
    assert _open_p0_p1(defects) == ["D001"]
    assert _open_p0_p1(_defects(header + "| D002 | P2 | Fixture: copy | 2026-10-21 | PO | OPEN | none |\n")) == []
    assert _defects(header) == []
    register = (
        "| G05 | PASSED | Scope met except B03 (cloud account) |\n| G06 | DONE | fixture |\n| G07 | PASSED | all |\n"
    )
    problems = _gate_problems(register, ["B03"])
    assert problems == ["G05 is PASSED while it names open blockers ['B03']", "G06: 'DONE' is not a §7.2 gate state"]
