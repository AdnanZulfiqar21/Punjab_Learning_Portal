"""P09.S3.T1 (ALLOCATION-01): a test pattern's section may set a difficulty mix. Counts are allocated by
largest-remainder rounding (always the section's total, ties to the easier band), each band draws only variants
reviewed at that difficulty, the draw is reproducible from its seed, and a band that runs short refuses the test
instead of borrowing. Technical fixture data only: families and versions are stand-in objects, and the fixture
questions carry no difficulty."""

# ruff: noqa: S311 - seeded, reproducible test data, never secrets
from __future__ import annotations

import random
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from portal_api.modules.assessment import mocks
from portal_api.modules.assessment.profiles import parse_rules
from tests.test_attempts import _learner
from tests.test_mocks import _mock, _publish_profile


def test_largest_remainder_rounding_is_exact_and_deterministic() -> None:
    assert mocks.allocate(10, {"easy": 30, "medium": 50, "hard": 20}) == {"easy": 3, "medium": 5, "hard": 2}
    assert mocks.allocate(7, {"easy": 33, "medium": 33, "hard": 34}) == {"easy": 2, "medium": 2, "hard": 3}
    assert mocks.allocate(1, {"easy": 50, "medium": 50}) == {"easy": 1, "medium": 0, "hard": 0}  # tie: easier band
    rng = random.Random(3)
    for _ in range(500):
        a = rng.randint(0, 100)
        b = rng.randint(0, 100 - a)
        mix = {"easy": a, "medium": b, "hard": 100 - a - b}
        n = rng.randint(1, 60)
        counts = mocks.allocate(n, mix)
        assert sum(counts.values()) == n, (n, mix)
        for band, k in counts.items():
            exact = n * mix[band] / 100
            assert int(exact) <= k <= int(exact) + 1, (n, mix)  # never more than one away from its exact share


def _pool(rng: random.Random, bands: dict[str, int]) -> dict[uuid.UUID, list[Any]]:
    """Families whose variants are reviewed at one difficulty, plus some with none."""
    pool: dict[uuid.UUID, list[Any]] = {}
    for band, n in bands.items():
        for _ in range(n):
            meta = {"difficulty": band} if band != "unrated" else {}
            body = {"options": [{"id": "a"}, {"id": "b"}], "metadata": meta}
            pool[uuid.UUID(int=rng.getrandbits(128))] = [
                (SimpleNamespace(id=uuid.UUID(int=rng.getrandbits(128))), SimpleNamespace(body=body))
            ]
    return pool


def test_each_band_draws_its_allocation_reproducibly() -> None:
    mix = {"easy": 30, "medium": 50, "hard": 20}
    for seed in range(200):
        rng = random.Random(seed)
        pool = _pool(rng, {"easy": 6, "medium": 8, "hard": 4, "unrated": 5})
        [(picks, reused)] = mocks.select_sections([(10, pool)], set(), seed, [mix])
        got = [mocks.difficulty(p[2]) for p in picks]
        assert {b: got.count(b) for b in mocks.BANDS} == {"easy": 3, "medium": 5, "hard": 2}, seed
        assert len({p[0] for p in picks}) == 10 and reused == 0, seed  # distinct families; unrated never used
        again = mocks.select_sections([(10, dict(reversed(list(pool.items()))))], set(), seed, [mix])
        assert [p[0] for p in again[0][0]] == [p[0] for p in picks], seed  # same seed, same draw, any pool order


def test_a_band_takes_the_variant_reviewed_at_its_difficulty() -> None:
    rng = random.Random(4)
    pool: dict[uuid.UUID, list[Any]] = {}
    for _ in range(8):  # each family has an easy and a hard sibling variant
        pool[uuid.UUID(int=rng.getrandbits(128))] = [
            (
                SimpleNamespace(id=uuid.UUID(int=rng.getrandbits(128))),
                SimpleNamespace(body={"options": [{"id": "a"}, {"id": "b"}], "metadata": {"difficulty": band}}),
            )
            for band in ("easy", "hard")
        ]
    for seed in range(50):
        [(picks, _)] = mocks.select_sections([(4, pool)], set(), seed, [{"hard": 100}])
        assert [mocks.difficulty(p[2]) for p in picks] == ["hard"] * 4, seed


def test_a_short_band_refuses_instead_of_borrowing() -> None:
    pool = _pool(random.Random(1), {"easy": 20, "hard": 1, "unrated": 20})
    with pytest.raises(mocks.SectionShortage) as short:
        mocks.select_sections([(10, pool)], set(), 5, [{"easy": 70, "hard": 30}])
    assert (short.value.band, short.value.needed, short.value.available) == ("hard", 3, 1)


def test_a_section_without_a_mix_draws_exactly_as_before() -> None:
    rng = random.Random(9)
    pool = _pool(rng, {"easy": 3, "unrated": 9})
    assert [p[0] for p in mocks.select_sections([(6, pool)], set(), 11)[0][0]] == [
        p[0] for p in mocks.select_sections([(6, pool)], set(), 11, [None])[0][0]
    ]


def test_a_mix_must_add_up_to_100() -> None:
    section = {"subject": "physics", "grades": [11], "questions": 4}
    base = {
        "source_url": "https://example.invalid/fx",
        "source_note": "Fixture: technical pattern.",
        "duration_minutes": 30,
    }
    _, errors = parse_rules(
        {**base, "sections": [{**section, "difficulty_mix": {"easy": 50, "hard": 40}}]}, {"physics"}
    )
    assert any("add up to 100" in e for e in errors)
    rules, errors = parse_rules(
        {**base, "sections": [{**section, "difficulty_mix": {"easy": 60, "hard": 40}}]}, {"physics"}
    )
    assert rules is not None and not errors


def test_a_mock_whose_band_has_no_reviewed_questions_is_refused_by_name(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    code = _publish_profile(
        client, db, [{"subject": "physics", "grades": [11], "questions": 2, "difficulty_mix": {"easy": 50, "hard": 50}}]
    )
    learner = _learner(client)
    ready = client.get(f"/v1/mocks/{code}/readiness", headers=learner.headers).json()
    assert ready["ready"] is False  # the fixture questions carry no difficulty
    assert [b["difficulty"] for b in ready["sections"][0]["bands"]] == ["easy", "hard"]
    r = _mock(client, learner, code)
    assert r.status_code == 422 and r.json()["code_reason"] == "POOL_SHORTAGE"
    assert r.json()["sections"][0]["difficulty"] == "easy" and r.json()["sections"][0]["available"] == 0
