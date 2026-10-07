"""Deterministic scoring of a frozen final-answer ledger (roadmap P10.S3.T2, §5.7).

Pure function: the same ledger, frozen keys, pinned marking rule and effective adjudication set always give the same
result. Original keys and evidence are never mutated; adjudications are separate inputs (none exist yet in v1).
Percentages use decimal half-up rounding to 2 places. A zero remaining maximum is NOT_SCORABLE (no division by zero).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any


@dataclass(frozen=True)
class ItemKey:
    position: int
    correct_option_id: str
    option_ids: tuple[str, ...]
    marks: int


@dataclass(frozen=True)
class Adjudication:
    """A reviewed correction for one item (§5.7): EXCLUDE, CREDIT_ALL or KEY_CORRECTION (with a corrected key)."""

    position: int
    treatment: str
    corrected_option_id: str | None = None


@dataclass(frozen=True)
class Result:
    status: str  # scored | not_scorable
    raw: int
    maximum: int
    percentage: Decimal | None
    items: list[dict[str, Any]]


def adjudication_hash(adjudications: list[Adjudication]) -> str:
    canonical = sorted((a.position, a.treatment, a.corrected_option_id or "") for a in adjudications)
    return hashlib.sha256(json.dumps(canonical).encode()).hexdigest()


def ledger_hash(answers: dict[int, str | None]) -> str:
    canonical = sorted((p, o or "") for p, o in answers.items())
    return hashlib.sha256(json.dumps(canonical).encode()).hexdigest()


def score(
    keys: list[ItemKey],
    answers: dict[int, str | None],
    *,
    negative_marks: int = 0,
    adjudications: list[Adjudication] | None = None,
) -> Result:
    by_pos = {a.position: a for a in adjudications or []}
    raw = 0
    maximum = 0
    items: list[dict[str, Any]] = []
    for k in sorted(keys, key=lambda x: x.position):
        chosen = answers.get(k.position)
        if chosen is not None and chosen not in k.option_ids:
            chosen = None  # an invalid stored option counts as blank (never happens for admitted ops)
        adj = by_pos.get(k.position)
        treatment = adj.treatment if adj else "NONE"
        key = (
            adj.corrected_option_id
            if adj and adj.treatment == "KEY_CORRECTION" and adj.corrected_option_id
            else (k.correct_option_id)
        )
        if treatment == "EXCLUDE":
            items.append(_row(k, chosen, None, 0, 0, treatment))
            continue
        maximum += k.marks
        if treatment == "CREDIT_ALL":
            earned = k.marks
            correct = None
        elif chosen is None:
            earned, correct = 0, False
        elif chosen == key:
            earned, correct = k.marks, True
        else:
            earned, correct = -negative_marks, False
        raw += earned
        items.append(_row(k, chosen, correct, earned, k.marks, treatment))
    if maximum == 0:
        return Result("not_scorable", raw, 0, None, items)
    pct = (Decimal(raw) * 100 / Decimal(maximum)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Result("scored", raw, maximum, pct, items)


def _row(
    k: ItemKey, chosen: str | None, correct: bool | None, earned: int, maximum: int, treatment: str
) -> dict[str, Any]:
    return {
        "position": k.position,
        "chosen": chosen,
        "correct": correct,
        "earned": earned,
        "max": maximum,
        "treatment": treatment,
    }
