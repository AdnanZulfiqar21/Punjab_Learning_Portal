"""Observed question statistics (roadmap P08.S4.T3; ITEM-STATS-01).

For each published version of a multiple-choice question, from finalised attempts (practice, mock and review), using
each attempt's current score version so corrections count:

* **observed difficulty:** the share of answered responses that were correct, with how many were left blank;
* **option choice rates:** how often each option was chosen, the key marked;
* **discrimination:** the point-biserial correlation between getting this question right and the rest of the
  attempt (the score without this question, as a share of its maximum), so a question doesn't correlate with itself.

Every figure carries its sample size. Responses scored under a void or credit-all correction are left out (they don't
show what the learner knew). Below `MIN_SAMPLE` answered responses nothing is judged: the statistics are shown as "too
few responses". From that size up, a question can be *flagged for a reviewer's look* (very hard, very easy, weak
discrimination, a distractor chosen more than the key, a distractor nobody chose). A flag is a prompt to review,
never a verdict: nothing is retired, edited or hidden automatically.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

MIN_SAMPLE = 30
HARD, EASY, WEAK = 0.2, 0.95, 0.15
COUNTED = ("NONE", "KEY_CORRECTION")  # no correction, or a corrected key; EXCLUDE and CREDIT_ALL say nothing


@dataclass(frozen=True)
class Response:
    chosen: str | None
    correct: bool
    rest: float | None  # the rest of the attempt as a share of its maximum (None when nothing else was scored)


def _point_biserial(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None  # everyone right (or wrong), or no spread in the rest: correlation is undefined
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / (sx * sy)


def summarise(responses: list[Response], key: str | None, options: list[str]) -> dict[str, Any]:
    answered = [r for r in responses if r.chosen is not None]
    n = len(answered)
    correct = sum(1 for r in answered if r.correct)
    counts = {o: sum(1 for r in answered if r.chosen == o) for o in options}
    pairs = [(1.0 if r.correct else 0.0, r.rest) for r in answered if r.rest is not None]
    disc = _point_biserial([p[0] for p in pairs], [p[1] for p in pairs]) if pairs else None
    out: dict[str, Any] = {
        "responses": len(responses),
        "answered": n,
        "blank": len(responses) - n,
        "difficulty": round(correct / n, 3) if n else None,
        "options": [
            {"option_id": o, "key": o == key, "chosen": counts[o], "rate": round(counts[o] / n, 3) if n else None}
            for o in options
        ],
        "discrimination": round(disc, 3) if disc is not None else None,
        "discrimination_sample": len(pairs),
        "enough": n >= MIN_SAMPLE,
        "flags": [],
    }
    if n < MIN_SAMPLE:
        return out
    flags = []
    p = correct / n
    if p < HARD:
        flags.append("very_hard")
    if p > EASY:
        flags.append("very_easy")
    if disc is not None and len(pairs) >= MIN_SAMPLE and disc < WEAK:
        flags.append("weak_discrimination")
    key_count = counts.get(key or "", 0)
    if any(c > key_count for o, c in counts.items() if o != key):
        flags.append("distractor_beats_key")
    if any(c == 0 for o, c in counts.items() if o != key):
        flags.append("unused_distractor")
    out["flags"] = flags
    return out


def _responses(db: Session, item_id: uuid.UUID) -> dict[uuid.UUID, list[Response]]:
    from portal_api.modules.assessment.models import Attempt, FormItem, ScoreVersion

    latest = (
        select(ScoreVersion.attempt_id, func.max(ScoreVersion.version).label("v"))
        .group_by(ScoreVersion.attempt_id)
        .subquery()
    )
    rows = db.execute(
        select(FormItem.version_id, FormItem.position, ScoreVersion.raw, ScoreVersion.maximum, ScoreVersion.items)
        .join(Attempt, Attempt.form_id == FormItem.form_id)
        .join(latest, latest.c.attempt_id == Attempt.id)
        .join(ScoreVersion, (ScoreVersion.attempt_id == Attempt.id) & (ScoreVersion.version == latest.c.v))
        .where(FormItem.item_id == item_id, Attempt.status == "finalised")
    ).all()
    out: dict[uuid.UUID, list[Response]] = {}
    for version_id, position, raw, maximum, items in rows:
        row = next((i for i in items or [] if i.get("position") == position), None)
        if row is None or row.get("treatment") not in COUNTED:
            continue
        rest_max = (maximum or 0) - int(row.get("max") or 0)
        rest = ((raw or 0) - int(row.get("earned") or 0)) / rest_max if rest_max > 0 else None
        out.setdefault(version_id, []).append(Response(row.get("chosen"), bool(row.get("correct")), rest))
    return out


def for_item(db: Session, item_id: uuid.UUID) -> list[dict[str, Any]]:
    """Statistics per version of this question that learners have answered, newest version first."""
    from portal_api.modules.content.models import ContentVersion

    by_version = _responses(db, item_id)
    out = []
    for version_id, responses in by_version.items():
        v = db.get(ContentVersion, version_id)
        if v is None:
            continue
        body = v.body if isinstance(v.body, dict) else {}
        options = [str(o.get("id")) for o in body.get("options", []) if isinstance(o, dict) and o.get("id")]
        out.append({"version": v.number, **summarise(responses, body.get("correct_option_id"), options)})
    return sorted(out, key=lambda s: -int(s["version"]))


def flagged(db: Session, grade: int, subject: str) -> list[dict[str, Any]]:
    """Questions in this class and subject with enough responses on some version and at least one flag."""
    from portal_api.modules.assessment.models import Attempt, FormItem
    from portal_api.modules.content.models import ContentItem

    candidates = db.execute(
        select(FormItem.item_id, func.count())
        .join(Attempt, Attempt.form_id == FormItem.form_id)
        .where(FormItem.grade_number == grade, FormItem.subject_code == subject, Attempt.status == "finalised")
        .group_by(FormItem.item_id)
        .having(func.count() >= MIN_SAMPLE)
    ).all()
    out = []
    for item_id, _ in candidates:
        stats = [s for s in for_item(db, item_id) if s["flags"]]
        item = db.get(ContentItem, item_id)
        if stats and item is not None:
            out.append(
                {"item_id": str(item_id), "title": item.title, "availability": item.availability, "versions": stats}
            )
    return out


class OptionStat(BaseModel):
    option_id: str
    key: bool
    chosen: int
    rate: float | None


class ItemStatsOut(BaseModel):
    version: int
    responses: int = Field(description="Finalised attempts that included this version (excluding voided scoring)")
    answered: int
    blank: int
    difficulty: float | None = Field(description="Share of answered responses that were correct")
    options: list[OptionStat]
    discrimination: float | None = Field(description="Point-biserial with the rest of the attempt; null if undefined")
    discrimination_sample: int
    enough: bool = Field(description=f"At least {MIN_SAMPLE} answered responses: below that nothing is judged")
    flags: list[str] = Field(description="Prompts for a reviewer's look, never a verdict")


class FlaggedOut(BaseModel):
    item_id: uuid.UUID
    title: str
    availability: str
    versions: list[ItemStatsOut]
