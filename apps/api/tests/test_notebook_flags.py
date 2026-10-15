"""P12.S3.T1 (NOTEBOOK-FLAGS-01): questions a learner flagged as unsure are collected in the notebook, answered or
not, right or wrong, without counting a miss; a flagged correct answer in review doesn't move the entry on; flagging a
mastered question opens it again. Technical fixture questions only."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.test_attempts import POOL, _form, _learner, _op, _save_ops, _start
from tests.test_mcq_corrections import _keys
from tests.test_mistake_notebook import _make_due, _submit


def _answer(client: TestClient, who: Any, form_id: str, attempt: dict[str, Any], plan: dict[int, str]) -> None:
    """plan: position -> "right", "wrong" or "skip"."""
    keys = _keys(form_id)
    ops = []
    for item in attempt["items"]:
        p = item["position"]
        choice = plan.get(p, "right")
        if choice == "skip":
            continue
        wrong = next(o["id"] for o in item["options"] if o["id"] != keys[p])
        ops.append(_op(p, 1, keys[p] if choice == "right" else wrong))
    assert _save_ops(client, who, attempt["id"], *ops).status_code == 200


def _flag(client: TestClient, who: Any, attempt_id: str, positions: list[int]) -> None:
    r = client.put(f"/v1/attempts/{attempt_id}/flags", headers=who.headers, json={"positions": positions})
    assert r.status_code == 200, r.text


def _book(client: TestClient, who: Any) -> dict[int, dict[str, Any]]:
    return {e["position"]: e for e in client.get("/v1/me/notebook", headers=who.headers).json()}


def test_flagged_questions_are_collected_without_counting_a_miss(client: TestClient, physics: dict[str, Any]) -> None:
    learner = _learner(client)
    form = _form(client, learner, physics["chapter"], count=4).json()
    attempt = _start(client, learner, form["id"])
    _answer(client, learner, form["id"], attempt, {1: "right", 2: "skip", 3: "wrong", 4: "right"})
    _flag(client, learner, attempt["id"], [1, 2, 3])
    _submit(client, learner, attempt["id"])

    book = _book(client, learner)
    assert set(book) == {1, 2, 3}  # the confident correct answer (4) is not collected
    right_but_unsure, unanswered_and_flagged, wrong_and_flagged = book[1], book[2], book[3]
    for e in (right_but_unsure, unanswered_and_flagged):
        assert (e["status"], e["misses"], e["flagged"]) == ("open", 0, True)
        assert e["why"].startswith("Flagged as unsure on") and "after 1 day" in e["why"]
    assert (wrong_and_flagged["misses"], wrong_and_flagged["flagged"]) == (1, True)
    assert wrong_and_flagged["why"].startswith("Missed on")


def test_review_moves_on_only_on_a_confident_answer_and_a_flag_reopens_mastery(
    client: TestClient, physics: dict[str, Any]
) -> None:
    learner = _learner(client)
    form = _form(client, learner, physics["chapter"], count=1).json()
    attempt = _start(client, learner, form["id"])
    _answer(client, learner, form["id"], attempt, {1: "right"})
    _flag(client, learner, attempt["id"], [1])
    _submit(client, learner, attempt["id"])
    [entry] = client.get("/v1/me/notebook", headers=learner.headers).json()
    assert entry["flagged"] is True

    def review(flag: bool, outcome: str = "right") -> dict[str, Any]:
        _make_due(learner.id)
        body = {"grade": 11, "subject": "physics", "count": 1}
        rv = client.post(
            "/v1/me/notebook/review", headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex}, json=body
        )
        assert rv.status_code == 201, rv.text
        ra = _start(client, learner, rv.json()["id"])
        _answer(client, learner, rv.json()["id"], ra, {1: outcome})
        if flag:
            _flag(client, learner, ra["id"], [1])
        _submit(client, learner, ra["id"])
        [after] = client.get("/v1/me/notebook", headers=learner.headers).json()
        return dict(after)

    unsure = review(flag=True)
    assert "after 1 day" in unsure["why"] and unsure["why"].startswith("Flagged as unsure")  # no step forward
    assert unsure["misses"] == 0
    sure = review(flag=False)
    assert "after 3 day" in sure["why"] and sure["why"].startswith("Answered correctly in review")

    # Entries are derived by replaying every response, so mastery takes the remaining confident reviews (7 and 14 days).
    assert [review(flag=False)["status"] for _ in range(3)] == ["open", "open", "mastered"]

    # Flagged again in an ordinary test: back into review, still no miss.
    again_form = _form(client, learner, physics["chapter"], count=POOL).json()
    again = _start(client, learner, again_form["id"])
    _answer(client, learner, again_form["id"], again, {})
    _flag(client, learner, again["id"], [p["position"] for p in again["items"]])
    _submit(client, learner, again["id"])
    reopened = next(e for e in client.get("/v1/me/notebook", headers=learner.headers).json() if e["id"] == entry["id"])
    assert (reopened["status"], reopened["misses"]) == ("open", 0)
    assert reopened["why"].startswith("Flagged as unsure") and "after 1 day" in reopened["why"]
