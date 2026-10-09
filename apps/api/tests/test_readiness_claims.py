"""Readiness claims need evidence (roadmap §2.3; READINESS-01).

`docs/project/RELEASE_CHECKLIST.md` records three states: Platform Ready, Content Ready and Public Launch Ready.
This guard fails CI if a state is claimed (anything other than NOT_READY) while any of its own checklist items is
unticked, or while any blocker in `docs/project/BLOCKERS.md` is still BLOCKED_EXTERNAL or BLOCKED_DECISION. A
blocker note is never passing evidence.
"""

from __future__ import annotations

import re
from pathlib import Path

DOCS = Path(__file__).resolve().parents[3] / "docs" / "project"
STATES = ("Platform Ready", "Content Ready", "Public Launch Ready")


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


def test_every_readiness_state_is_recorded() -> None:
    sections = _sections((DOCS / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8"))
    assert set(sections) == set(STATES)


def test_no_readiness_state_is_claimed_without_evidence() -> None:
    sections = _sections((DOCS / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8"))
    blockers = _open_blockers((DOCS / "BLOCKERS.md").read_text(encoding="utf-8"))
    wrong = []
    for state, (status, items) in sections.items():
        if status == "NOT_READY":
            continue
        unticked = [i for i in items if i.startswith("- [ ]")]
        if unticked or blockers:
            wrong.append(f"{state} is {status} with {len(unticked)} unticked items and open blockers {blockers}")
    assert wrong == []
