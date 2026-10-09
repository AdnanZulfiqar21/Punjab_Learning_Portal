"""Learning evidence classification, `evidence_rules_v2` (roadmap §6.6, P12.S2.T1/T2/T4; EVIDENCE-RULES-01).

A pure function over eligible binary MCQ responses, so every rule is testable exactly:

* **Evidence unit:** one finalised scored response per (attempt, question, outcome) under its latest score version.
  Blanks, excluded and credited questions, staff accounts and void attempts contribute nothing. Save revisions are
  never responses.
* **Window:** the 90 x 24 hours before the evaluation time (UTC).
* **Weights:** age x hint x exposure.
  - Age is 1 up to 45 days, 0.5 up to 90 days, otherwise 0.
  - Hint is 0.5 when hinted, otherwise 1.
  - Exposure is 0.25 if the learner answered a question of the same canonical family in the 30 days before this
    response, otherwise 1.
* **Family cap:** per outcome, one family contributes at most 2 effective weight, scaled proportionally.
* **Independent evidence:** unhinted responses with no same-family response in the preceding 30 days, weighted by the
  same age rule and family cap.
* **Classification**, first matching rule:
  1. `insufficient_evidence` — total weight < 6 or fewer than 3 contributing families;
  2. `demonstrated` — independent weight ≥ 6 from ≥ 3 families, independent weighted accuracy ≥ 80%, and ≥ 2
     distinct families with independent correct responses in the last 30 days;
  3. `developing` — with one or more reasons (accuracy below threshold, more independent practice needed, recent
     confirmation needed).

Total weighted accuracy guides revision only; it never switches demonstration on.

*Provisional mappings:* an outcome is the question's curriculum topic, else its chapter, until verified exam outcomes
exist (B02). No hint feature exists, so the hint factor is always 1.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

RULES_VERSION = "evidence_rules_v2"
WINDOW = timedelta(days=90)
FULL_AGE = timedelta(days=45)
EXPOSURE = timedelta(days=30)
RECENT = timedelta(days=30)
FAMILY_CAP = 2.0
MIN_WEIGHT = 6.0
MIN_FAMILIES = 3
MIN_ACCURACY = 0.8
MIN_RECENT_FAMILIES = 2


@dataclass(frozen=True)
class Response:
    family_id: uuid.UUID
    outcome_id: uuid.UUID
    at: datetime
    correct: bool
    hinted: bool = False


@dataclass
class Classification:
    outcome_id: uuid.UUID
    state: str
    reasons: list[str] = field(default_factory=list)
    total_weight: float = 0.0
    families: int = 0
    weighted_accuracy: float | None = None
    independent_weight: float = 0.0
    independent_families: int = 0
    independent_accuracy: float | None = None
    recent_independent_correct_families: int = 0
    responses: int = 0


def _age(at: datetime, now: datetime) -> float:
    age = now - at
    if age < timedelta(0) or age > WINDOW:
        return 0.0
    return 1.0 if age <= FULL_AGE else 0.5


def _capped(weights: list[tuple[uuid.UUID, float, bool]]) -> list[tuple[uuid.UUID, float, bool]]:
    """Scale each family's weights so the family contributes at most FAMILY_CAP."""
    per_family: dict[uuid.UUID, float] = defaultdict(float)
    for fam, w, _ in weights:
        per_family[fam] += w
    out = []
    for fam, w, correct in weights:
        total = per_family[fam]
        out.append((fam, w * (FAMILY_CAP / total) if total > FAMILY_CAP else w, correct))
    return out


def classify(responses: list[Response], now: datetime) -> dict[uuid.UUID, Classification]:
    """Classify every outcome that has at least one response in the window."""
    in_window = sorted((r for r in responses if _age(r.at, now) > 0), key=lambda r: r.at)
    # Exposure looks at all of the learner's responses (any outcome) before each response, by canonical family.
    by_family_times: dict[uuid.UUID, list[datetime]] = defaultdict(list)
    for r in sorted(responses, key=lambda r: r.at):
        by_family_times[r.family_id].append(r.at)

    def exposed(r: Response) -> bool:
        return any(r.at - EXPOSURE <= t < r.at for t in by_family_times[r.family_id])

    per_outcome: dict[uuid.UUID, list[Response]] = defaultdict(list)
    for r in in_window:
        per_outcome[r.outcome_id].append(r)
    out: dict[uuid.UUID, Classification] = {}
    for outcome, rs in per_outcome.items():
        all_w = _capped(
            [
                (r.family_id, _age(r.at, now) * (0.5 if r.hinted else 1.0) * (0.25 if exposed(r) else 1.0), r.correct)
                for r in rs
            ]
        )
        independent = [r for r in rs if not r.hinted and not exposed(r)]
        ind_w = _capped([(r.family_id, _age(r.at, now), r.correct) for r in independent])
        total = sum(w for _, w, _ in all_w)
        fams = len({f for f, w, _ in all_w if w > 0})
        acc = sum(w for _, w, c in all_w if c) / total if total else None
        ind_total = sum(w for _, w, _ in ind_w)
        ind_fams = len({f for f, w, _ in ind_w if w > 0})
        ind_acc = sum(w for _, w, c in ind_w if c) / ind_total if ind_total else None
        recent = len({r.family_id for r in independent if r.correct and now - r.at <= RECENT})
        c = Classification(
            outcome_id=outcome,
            state="",
            total_weight=round(total, 4),
            families=fams,
            weighted_accuracy=round(acc, 4) if acc is not None else None,
            independent_weight=round(ind_total, 4),
            independent_families=ind_fams,
            independent_accuracy=round(ind_acc, 4) if ind_acc is not None else None,
            recent_independent_correct_families=recent,
            responses=len(rs),
        )
        if total < MIN_WEIGHT or fams < MIN_FAMILIES:
            c.state = "insufficient_evidence"
            c.reasons = ["Not enough recent evidence yet: practise more questions from different question families."]
        elif (
            ind_total >= MIN_WEIGHT
            and ind_fams >= MIN_FAMILIES
            and ind_acc is not None
            and ind_acc >= MIN_ACCURACY
            and recent >= MIN_RECENT_FAMILIES
        ):
            c.state = "demonstrated"
        else:
            c.state = "developing"
            if ind_acc is not None and ind_acc < MIN_ACCURACY:
                c.reasons.append("Accuracy on first-time questions is below 80%.")
            if ind_total < MIN_WEIGHT or ind_fams < MIN_FAMILIES:
                c.reasons.append("More practice on questions you haven't seen recently is needed.")
            if recent < MIN_RECENT_FAMILIES:
                c.reasons.append("Recent confirmation needed: answer two different questions correctly this month.")
            if not c.reasons:  # every developing record carries a reason
                c.reasons.append("More practice on questions you haven't seen recently is needed.")
        out[outcome] = c
    return out


def learner_responses(db: Any, user_id: uuid.UUID, now: datetime) -> list[Response]:
    """Eligible responses from each finalised attempt's latest score version (staff accounts give none)."""
    from sqlalchemy import func, select

    from portal_api.modules.assessment.models import Attempt, FormItem, ScoreVersion
    from portal_api.modules.content.models import ContentItem
    from portal_api.modules.identity.models import StaffRoleGrant

    if db.scalar(
        select(func.count(StaffRoleGrant.id)).where(
            StaffRoleGrant.user_id == user_id, StaffRoleGrant.revoked_at.is_(None)
        )
    ):
        return []  # staff and technical accounts contribute no knowledge evidence
    from portal_api.modules.assessment.sessions import held_forms

    held = held_forms(db, user_id)  # OCT9-01: a held scheduled mock is not evidence until its results are released
    latest = (
        select(ScoreVersion.attempt_id, func.max(ScoreVersion.version).label("v"))
        .group_by(ScoreVersion.attempt_id)
        .subquery()
    )
    rows = db.execute(
        select(Attempt, ScoreVersion)
        .join(latest, latest.c.attempt_id == Attempt.id)
        .join(ScoreVersion, (ScoreVersion.attempt_id == Attempt.id) & (ScoreVersion.version == latest.c.v))
        .where(
            Attempt.user_id == user_id, Attempt.status == "finalised", Attempt.finalised_at >= now - WINDOW - EXPOSURE
        )
    ).all()
    rows = [(a, sc) for a, sc in rows if a.form_id not in held]
    # One query for every form's items and their outcome (no per-attempt or per-item round trips).
    meta: dict[tuple[uuid.UUID, int], tuple[uuid.UUID, uuid.UUID]] = {
        (form_id, pos): (family, outcome)
        for form_id, pos, family, outcome in db.execute(
            select(
                FormItem.form_id,
                FormItem.position,
                FormItem.family_id,
                func.coalesce(ContentItem.topic_id, ContentItem.chapter_id),
            )
            .join(ContentItem, ContentItem.id == FormItem.item_id)
            .where(FormItem.form_id.in_({a.form_id for a, _ in rows}))
        ).all()
    } if rows else {}  # fmt: skip
    out: list[Response] = []
    for attempt, score in rows:
        for row in score.items:
            if row.get("treatment") in ("EXCLUDE", "CREDIT_ALL") or row.get("chosen") is None:
                continue
            m = meta.get((attempt.form_id, int(row["position"])))
            if m is None:
                continue
            out.append(
                Response(family_id=m[0], outcome_id=m[1], at=attempt.finalised_at, correct=bool(row.get("correct")))
            )
    return out
