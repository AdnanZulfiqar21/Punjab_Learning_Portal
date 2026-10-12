"""P08.S4.T3 (ITEM-STATS-01): observed question statistics. Difficulty, option choice and discrimination are computed
from finalised attempts with their sample sizes; nothing is judged below the minimum sample, and from it a question is
only *flagged for review*, never retired or changed. The maths is checked on synthetic responses; the end-to-end path
on real fixture attempts. Technical fixture questions and accounts only."""

from __future__ import annotations

import statistics
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from portal_api.modules.content import item_stats
from portal_api.modules.content.item_stats import MIN_SAMPLE, Response, summarise
from tests.test_attempts import POOL, _form, _learner, _op, _save_ops, _start, publish_physics_pool
from tests.test_content_workflow import Staff

OPTIONS = ["o1", "o2", "o3", "o4"]


def _many(spec: list[tuple[str | None, bool, float]], times: int = 1) -> list[Response]:
    return [Response(chosen, correct, rest) for chosen, correct, rest in spec] * times


def test_the_numbers_match_their_definitions() -> None:
    # 40 answered: strong learners (high rest) mostly right, weak ones mostly on o2.
    responses = _many([("o1", True, 0.9), ("o1", True, 0.8), ("o2", False, 0.3), ("o3", False, 0.4)], 10)
    responses += _many([(None, False, 0.5)], 3)  # blanks count as responses, not as answered
    s = summarise(responses, "o1", OPTIONS)
    assert (s["responses"], s["answered"], s["blank"]) == (43, 40, 3)
    assert s["difficulty"] == 0.5
    rates = {o["option_id"]: (o["chosen"], o["rate"], o["key"]) for o in s["options"]}
    assert rates == {"o1": (20, 0.5, True), "o2": (10, 0.25, False), "o3": (10, 0.25, False), "o4": (0, 0.0, False)}
    answered = [r for r in responses if r.chosen is not None]
    expected = statistics.correlation([1.0 if r.correct else 0.0 for r in answered], [r.rest or 0.0 for r in answered])
    assert s["discrimination"] == round(expected, 3) and s["discrimination"] > 0.5 and s["discrimination_sample"] == 40
    assert s["enough"] and s["flags"] == ["unused_distractor"]  # o4 was never chosen


def test_flags_need_enough_responses_and_say_what_to_look_at() -> None:
    tiny = summarise(_many([("o2", False, 0.9), ("o1", True, 0.1)], 5), "o1", OPTIONS)
    assert not tiny["enough"] and tiny["flags"] == [] and tiny["answered"] == 10 < MIN_SAMPLE  # no claims from 10
    hard = summarise(
        _many([("o2", False, 0.7), ("o3", False, 0.6), ("o4", False, 0.5), ("o2", False, 0.4)], 9)
        + _many([("o1", True, 0.9)], 4),
        "o1",
        OPTIONS,
    )
    assert "very_hard" in hard["flags"] and "distractor_beats_key" in hard["flags"]
    flat = summarise(
        _many([("o1", True, 0.5), ("o2", False, 0.5), ("o1", True, 0.6), ("o3", False, 0.6)], 10), "o1", OPTIONS
    )
    assert "weak_discrimination" in flat["flags"]
    easy = summarise(_many([("o1", True, 0.5), ("o1", True, 0.7)], 20), "o1", OPTIONS)
    assert "very_easy" in easy["flags"] and easy["discrimination"] is None  # everyone right: undefined, not zero


@pytest.fixture(scope="module")
def stats_pool(client: TestClient) -> dict[str, Any]:
    return publish_physics_pool(client, 6)  # its own chapter: answers below shape these statistics


def test_statistics_come_from_finalised_attempts_and_stay_with_their_scope(
    client: TestClient, db: Session, stats_pool: dict[str, Any]
) -> None:
    target = stats_pool["ids"][0]
    key = stats_pool["keys"][target]
    wrong = next(o for o in OPTIONS if o != key)
    for i, choice in enumerate([key, key, wrong, None]):
        learner = _learner(client)
        form = _form(client, learner, stats_pool["chapter"], count=POOL).json()
        attempt = _start(client, learner, form["id"])
        position = db.execute(
            text("select position from form_item where form_id = :f and item_id = :i"), {"f": form["id"], "i": target}
        ).scalar_one()
        if choice is not None:
            assert _save_ops(client, learner, attempt["id"], _op(position, 1, choice)).status_code == 200
        done = client.post(
            f"/v1/attempts/{attempt['id']}/submit",
            headers=learner.headers,
            json={"idempotency_key": f"stats-{uuid.uuid4().hex[:12]}-{i}"},
        )
        assert done.status_code == 200, done.text
    unfinished = _learner(client)  # an attempt still in progress never counts
    _start(client, unfinished, _form(client, unfinished, stats_pool["chapter"], count=POOL).json()["id"])

    reviewer = Staff(client, db, ["subject_reviewer"], {"grades": [11], "subjects": ["physics"]})
    r = client.get(f"/v1/studio/items/{target}/statistics", headers=reviewer.headers)
    assert r.status_code == 200 and r.headers["cache-control"] == "private, no-store", r.text
    [s] = r.json()
    assert (s["responses"], s["answered"], s["blank"]) == (4, 3, 1)
    assert s["difficulty"] == round(2 / 3, 3) and s["enough"] is False and s["flags"] == []
    chosen = {o["option_id"]: o["chosen"] for o in s["options"]}
    assert chosen[key] == 2 and chosen[wrong] == 1

    outsider = Staff(client, db, ["subject_reviewer"], {"grades": [12], "subjects": ["biology"]})
    assert client.get(f"/v1/studio/items/{target}/statistics", headers=outsider.headers).status_code == 404
    flagged = client.get(
        "/v1/studio/statistics/flagged", params={"grade": 11, "subject": "physics"}, headers=reviewer.headers
    )
    assert flagged.status_code == 200 and all(f["item_id"] != target for f in flagged.json())  # too few to judge
    other = {"grade": 12, "subject": "biology"}
    assert client.get("/v1/studio/statistics/flagged", params=other, headers=reviewer.headers).status_code == 404
    assert item_stats.MIN_SAMPLE == 30
