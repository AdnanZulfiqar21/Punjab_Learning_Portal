"""P09.S4.T2 (GENERATOR-PROPERTIES-01): property checks for practice and mock form selection over many seeded random
pools (no extra dependency), plus the profile rule that keeps mock sections from drawing the same question twice.
Each failure message carries its seed. Technical fixture data only: families and versions are stand-in objects."""

# ruff: noqa: S311 - seeded, reproducible test data, never secrets
from __future__ import annotations

import random
import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from portal_api.modules.assessment import forms, mocks
from portal_api.modules.assessment.profiles import parse_rules

CASES = 600


def _pool(rng: random.Random, families: list[uuid.UUID]) -> dict[uuid.UUID, list[Any]]:
    pool: dict[uuid.UUID, list[Any]] = {}
    for f in families:
        members = []
        for _ in range(rng.randint(1, 3)):  # sibling variants of one question
            options = [{"id": f"o{i}"} for i in range(rng.randint(2, 5))]
            body = {"options": options, "shuffle_options": rng.random() < 0.8}
            members.append((SimpleNamespace(id=uuid.UUID(int=rng.getrandbits(128))), SimpleNamespace(body=body)))
        pool[f] = members
    return pool


def _families(rng: random.Random, n: int) -> list[uuid.UUID]:
    return [uuid.UUID(int=rng.getrandbits(128)) for _ in range(n)]


def _check_picks(picks: list[Any], pool: dict[uuid.UUID, list[Any]], seed: int) -> None:
    for family, item, version, option_ids in picks:
        assert any(m[0] is item and m[1] is version for m in pool[family]), seed  # a variant of that family
        assert sorted(option_ids) == sorted(o["id"] for o in version.body["options"]), seed  # a permutation
        if not version.body["shuffle_options"]:
            assert option_ids == [o["id"] for o in version.body["options"]], seed


def test_practice_selection_is_exact_unique_and_reproducible() -> None:
    for seed in range(CASES):
        rng = random.Random(seed)
        pool = _pool(rng, _families(rng, rng.randint(0, 25)))
        count = rng.randint(1, 30)
        if count > len(pool):  # empty or short pools fail honestly, never a smaller test
            with pytest.raises(ValueError):
                forms.select_practice(pool, count, seed)
            continue
        picks = forms.select_practice(pool, count, seed)
        assert len(picks) == count and len({p[0] for p in picks}) == count, seed  # exact total, unique families
        _check_picks(picks, pool, seed)
        shuffled = dict(rng.sample(list(pool.items()), len(pool)))  # pool order never matters
        again = forms.select_practice(shuffled, count, seed)
        assert [(p[0], p[1].id, p[3]) for p in again] == [(p[0], p[1].id, p[3]) for p in picks], seed


def test_mock_selection_is_exact_unique_across_sections_and_prefers_unseen() -> None:
    for seed in range(CASES):
        rng = random.Random(seed)
        shared = _families(rng, rng.randint(0, 10))  # sections of one subject can share questions
        sections = []
        for _ in range(rng.randint(1, 4)):
            own = _families(rng, rng.randint(0, 15))
            fams = own + rng.sample(shared, rng.randint(0, len(shared)))
            sections.append((rng.randint(1, 8), _pool(rng, fams)))
        everything = {f for _, p in sections for f in p}
        seen = set(rng.sample(sorted(everything, key=str), rng.randint(0, len(everything))))
        try:
            chosen = mocks.select_sections(sections, seen, seed)
        except mocks.SectionShortage as short:
            assert short.section is not None, seed  # only when the distinct supply really runs out
            continue
        picked = [p[0] for picks, _ in chosen for p in picks]
        assert len(picked) == len(set(picked)), seed  # never the same question twice, even across sections
        for (n, pool), (picks, reused) in zip(sections, chosen, strict=True):
            assert len(picks) == n, seed
            _check_picks(picks, pool, seed)
            assert reused == sum(1 for p in picks if p[0] in seen), seed  # reuse is counted honestly
        reordered = [(n, dict(rng.sample(list(p.items()), len(p)))) for n, p in sections]  # pool order never matters
        again = mocks.select_sections(reordered, seen, seed)
        assert [[p[0] for p in s] for s, _ in again] == [[p[0] for p in s] for s, _ in chosen], seed


def test_unseen_questions_are_always_used_before_seen_ones() -> None:
    rng = random.Random(7)
    fams = _families(rng, 12)
    pool = _pool(rng, fams)
    seen = set(fams[:6])
    ((picks, reused),) = mocks.select_sections([(6, pool)], seen, 7)
    assert reused == 0 and not {p[0] for p in picks} & seen
    ((picks, reused),) = mocks.select_sections([(9, pool)], seen, 7)
    assert reused == 3 and len({p[0] for p in picks} & seen) == 3


RULES = {
    "source_url": "https://example.invalid/fixture",
    "source_note": "Fixture: technical pattern for tests.",
    "duration_minutes": 30,
}


def test_profile_sections_of_one_subject_cannot_share_classes() -> None:
    overlap = [
        {"subject": "physics", "grades": [11], "questions": 2},
        {"subject": "physics", "grades": [11, 12], "questions": 2},
    ]
    rules, errors = parse_rules({**RULES, "sections": overlap}, {"physics"})
    assert rules is None and any("overlap" in e for e in errors), errors
    apart = [
        {"subject": "physics", "grades": [11], "questions": 2},
        {"subject": "physics", "grades": [12], "questions": 2},
    ]
    assert parse_rules({**RULES, "sections": apart}, {"physics"})[1] == []


def test_a_new_pattern_needs_no_code_change() -> None:
    """A future profile (new code, more sections, other subjects and mixed classes) is pure data."""
    sections = [
        {"subject": s, "grades": g, "questions": q, "label": f"Part {i}"}
        for i, (s, g, q) in enumerate(
            [("physics", [11, 12], 40), ("chemistry", [11], 30), ("chemistry", [12], 30), ("biology", [11, 12], 80)],
            start=1,
        )
    ]
    rules, errors = parse_rules(
        {
            **RULES,
            "sections": sections,
            "negative_marks": 1,
            "marks_per_question": 4,
            "invalid_item_treatment": "CREDIT_ALL",
        },
        {"physics", "chemistry", "biology"},
    )
    assert errors == [] and rules is not None and sum(s.questions for s in rules.sections) == 180
