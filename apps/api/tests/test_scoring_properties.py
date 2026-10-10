"""P09.S4.T2 (PROPERTY-01): property checks for MCQ scoring over many seeded random cases (no extra dependency).
Each failure message carries its seed, so a case can be replayed exactly."""

# ruff: noqa: S311 - seeded, reproducible test data, never secrets
from __future__ import annotations

import random
from decimal import ROUND_HALF_UP, Decimal

from portal_api.modules.assessment import scoring
from portal_api.modules.assessment.scoring import Adjudication, ItemKey

CASES = 1500


def _case(seed: int) -> tuple[list[ItemKey], dict[int, str | None], int, list[Adjudication]]:
    rng = random.Random(seed)
    keys = []
    for p in range(1, rng.randint(1, 30) + 1):
        options = tuple(f"o{i}" for i in range(1, rng.randint(2, 6) + 1))
        keys.append(
            ItemKey(position=p, correct_option_id=rng.choice(options), option_ids=options, marks=rng.randint(1, 4))
        )
    answers: dict[int, str | None] = {}
    for k in keys:
        roll = rng.random()
        answers[k.position] = None if roll < 0.2 else ("zz" if roll < 0.25 else rng.choice(k.option_ids))
    adjudications = []
    for k in rng.sample(keys, rng.randint(0, min(3, len(keys)))):
        t = rng.choice(["EXCLUDE", "CREDIT_ALL", "KEY_CORRECTION"])
        adjudications.append(Adjudication(k.position, t, rng.choice(k.option_ids) if t == "KEY_CORRECTION" else None))
    return keys, answers, rng.choice([0, 0, 1]), adjudications


def test_totals_bounds_and_rounding_hold_for_every_case() -> None:
    for seed in range(CASES):
        keys, answers, neg, adjs = _case(seed)
        r = scoring.score(keys, answers, negative_marks=neg, adjudications=adjs)
        rows = r.items
        assert [x["position"] for x in rows] == sorted(k.position for k in keys), seed  # one row per key, in order
        assert r.raw == sum(x["earned"] for x in rows) and r.maximum == sum(x["max"] for x in rows), seed
        treat = {a.position: a.treatment for a in adjs}
        for k, x in zip(sorted(keys, key=lambda k: k.position), rows, strict=True):
            assert -neg <= x["earned"] <= k.marks, seed
            if treat.get(k.position) == "EXCLUDE":
                assert (x["earned"], x["max"]) == (0, 0), seed
            if x["chosen"] is None:
                assert x["earned"] >= 0, seed  # a blank (or an invalid stored option) is never penalised
        if r.maximum == 0:
            assert r.status == "not_scorable" and r.percentage is None, seed
        else:
            expected = (Decimal(r.raw) * 100 / Decimal(r.maximum)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            assert r.status == "scored" and r.percentage == expected, seed


def test_order_never_matters_and_scoring_is_deterministic() -> None:
    for seed in range(CASES):
        keys, answers, neg, adjs = _case(seed)
        base = scoring.score(keys, answers, negative_marks=neg, adjudications=adjs)
        rng = random.Random(seed + 10_000)
        shuffled_keys, shuffled_adjs = keys[:], adjs[:]
        rng.shuffle(shuffled_keys)
        rng.shuffle(shuffled_adjs)
        again = scoring.score(shuffled_keys, answers, negative_marks=neg, adjudications=shuffled_adjs)
        assert (again.raw, again.maximum, again.percentage, again.items) == (
            base.raw,
            base.maximum,
            base.percentage,
            base.items,
        ), seed
        assert scoring.adjudication_hash(adjs) == scoring.adjudication_hash(shuffled_adjs), seed
        assert scoring.ledger_hash(answers) == scoring.ledger_hash(dict(reversed(list(answers.items())))), seed


def test_a_correct_answer_never_lowers_the_score() -> None:
    for seed in range(CASES):
        keys, answers, neg, adjs = _case(seed)
        before = scoring.score(keys, answers, negative_marks=neg, adjudications=adjs).raw
        corrections = {a.position: a.corrected_option_id for a in adjs if a.treatment == "KEY_CORRECTION"}
        k = random.Random(seed + 20_000).choice(keys)
        fixed = {**answers, k.position: corrections.get(k.position) or k.correct_option_id}
        assert scoring.score(keys, fixed, negative_marks=neg, adjudications=adjs).raw >= before, seed
