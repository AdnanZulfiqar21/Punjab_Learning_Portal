"""Learner rechecks pinned to a released version (W06.S2.T1/T2, §20.10, decision RECHECK-01).

Technical fixtures only: the questions, rubrics and marks below verify software behaviour, not marking accuracy.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from tests.test_content_workflow import Staff
from tests.test_written_attempts import _learner, _map, _png, _seal, _start, _upload

SCOPE = {"grades": [12], "subjects": ["chemistry"]}


def _staff(client: TestClient, roles: list[str]) -> Staff:
    with get_sessionmaker()() as db:
        return Staff(client, db, roles, SCOPE)


def _sealed_two_question_script(client: TestClient, chapter: str, seed: int) -> tuple[Staff, dict[str, Any]]:
    learner = _learner(client)
    a = _start(client, learner, chapter, question_count=2)
    page = _upload(client, learner, a["id"], _png(seed=seed)).json()["pages"][0]["id"]
    slots = {k: {"pages": [page]} for k in ("1:a", "1:b", "2:a", "2:b")}
    m = _map(client, learner, a, slots).json()
    assert _seal(client, learner, a["id"], m["manifest_revision"]).status_code == 200
    return learner, a


def _awards(**units: int) -> dict[str, Any]:
    """{"q1": 100} -> awards for question 1 criterion a1 (others 0)."""
    return {k[1:]: {"a1": {"units": v}, "b1": {"units": 0}, "b2": {"units": 0}} for k, v in units.items()}


def _case(client: TestClient, who: Staff, attempt_id: str, kind: str) -> dict[str, Any]:
    return next(
        c
        for c in client.get("/v1/studio/written/queue", headers=who.headers).json()
        if c["reference"] == attempt_id[:8] and c["case_kind"] == kind
    )


def _mark(client: TestClient, who: Staff, attempt_id: str, kind: str, awards: dict[str, Any], **extra: Any) -> Any:
    case = _case(client, who, attempt_id, kind)
    lease = client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=who.headers)
    if lease.status_code != 200:
        return lease
    return client.post(
        f"/v1/studio/written/cases/{case['id']}/decision",
        headers=who.headers,
        json={"expected_version": lease.json()["version"], "release": True, "awards": awards, **extra},
    )


def _result(client: TestClient, learner: Staff, attempt_id: str) -> Any:
    return client.get(f"/v1/written-attempts/{attempt_id}/result", headers=learner.headers).json()


def _ask(client: TestClient, learner: Staff, attempt_id: str, positions: list[int], **extra: Any) -> Any:
    return client.post(
        f"/v1/written-attempts/{attempt_id}/recheck",
        headers=learner.headers,
        json={"reason": "Fixture: please look at this answer again", "positions": positions, **extra},
    )


def test_recheck_marks_only_requested_questions_and_appeals_follow_corrections(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed_two_question_script(client, published_written["chapter"], seed=301)
    first, second, third = (_staff(client, ["subject_reviewer"]) for _ in range(3))
    assert _mark(client, first, a["id"], "initial", _awards(q1=100, q2=100)).status_code == 200
    consumed = client.get("/v1/me/access", headers=learner.headers).json()["written_allowance"]["consumed"]

    state = _result(client, learner, a["id"])["recheck"]
    assert state["status"] == "available" and state["eligible_positions"] == [1, 2] and state["target_version"] == 1

    bad = _ask(client, learner, a["id"], [1], criteria={"1": ["zz"]})
    assert bad.status_code == 422  # unknown criterion
    req = _ask(client, learner, a["id"], [1], criteria={"1": ["a1"]})
    assert req.status_code == 200 and req.json()["positions"] == [1]
    assert _ask(client, learner, a["id"], [1]).status_code == 409  # duplicate while open

    assert _mark(client, first, a["id"], "recheck", _awards(q1=200)).status_code == 403  # original marker
    case = client.get(
        f"/v1/studio/written/cases/{_case(client, second, a['id'], 'recheck')['id']}", headers=second.headers
    ).json()
    assert case["recheck"]["positions"] == [1] and case["recheck"]["criteria"] == {"1": ["a1"]}
    assert case["recheck"]["carried_forward"] == {"2": 100} and case["recheck"]["can_expand"] is False

    outside = _mark(client, second, a["id"], "recheck", _awards(q1=200, q2=0))
    assert outside.status_code == 422  # question 2 is outside the learner's request
    widen = _mark(client, second, a["id"], "recheck", _awards(q1=200, q2=0), expand_positions=[2])
    assert widen.status_code == 403  # widening needs an academic adjudicator
    assert _mark(client, second, a["id"], "recheck", _awards(q1=200)).status_code == 200

    after = _result(client, learner, a["id"])
    assert [q["earned_units"] for q in after["questions"]] == [200, 100]  # question 2 kept exactly
    assert [h["total_units"] for h in after["history"]] == [200, 300]
    access = client.get("/v1/me/access", headers=learner.headers).json()["written_allowance"]
    assert access["consumed"] == consumed  # no second charge for the same original work

    # The correction changed question 1 only, so only question 1 can be appealed against it.
    state = after["recheck"]
    assert state["status"] == "available" and state["eligible_positions"] == [1] and state["target_version"] == 2
    again = _ask(client, learner, a["id"], [2])
    assert again.status_code == 422 and again.json()["eligible_positions"] == [1]
    assert _ask(client, learner, a["id"], [1]).status_code == 200
    assert _mark(client, second, a["id"], "recheck", _awards(q1=200)).status_code == 403  # marked it before
    upheld = {"1": {**_awards(q1=200)["1"], "a1": {"units": 200, "reason": "Fixture: reworded feedback"}}}
    assert _mark(client, third, a["id"], "recheck", upheld).status_code == 200  # upheld; only feedback reworded
    final = _result(client, learner, a["id"])
    assert final["recheck"]["status"] == "closed" and final["recheck"]["closed_reason"] == "no_corrected_questions"
    assert [h["case_kind"] for h in final["history"]] == ["initial", "recheck", "recheck"]


def test_concurrent_recheck_requests_open_exactly_one_case(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed_two_question_script(client, published_written["chapter"], seed=302)
    assert (
        _mark(client, _staff(client, ["subject_reviewer"]), a["id"], "initial", _awards(q1=0, q2=0)).status_code == 200
    )
    with ThreadPoolExecutor(max_workers=4) as pool:
        codes = sorted(pool.map(lambda p: _ask(client, learner, a["id"], [p]).status_code, [1, 2, 1, 2]))
    assert codes == [200, 409, 409, 409]
    with get_sessionmaker()() as db:
        n = db.execute(
            text("select count(*) from written_recheck_request where attempt_id = :a"), {"a": a["id"]}
        ).scalar()
    assert n == 1


def test_adjudicator_widens_a_recheck_only_with_a_reason(client: TestClient, published_written: dict[str, Any]) -> None:
    learner, a = _sealed_two_question_script(client, published_written["chapter"], seed=303)
    assert (
        _mark(client, _staff(client, ["subject_reviewer"]), a["id"], "initial", _awards(q1=100, q2=100)).status_code
        == 200
    )
    assert _ask(client, learner, a["id"], [1]).status_code == 200
    adjudicator = _staff(client, ["academic_adjudicator"])
    no_reason = _mark(client, adjudicator, a["id"], "recheck", _awards(q1=100, q2=0), expand_positions=[2])
    assert no_reason.status_code == 422
    ok = _mark(
        client,
        adjudicator,
        a["id"],
        "recheck",
        _awards(q1=100, q2=0),
        expand_positions=[2],
        expansion_reason="Fixture: the same unit error appears in question 2.",
    )
    assert ok.status_code == 200, ok.text
    assert [q["earned_units"] for q in _result(client, learner, a["id"])["questions"]] == [100, 0]
    with get_sessionmaker()() as db:
        row = db.execute(
            text(
                "select expanded_positions, expansion_reason, status from written_recheck_request where attempt_id = :a"
            ),
            {"a": a["id"]},
        ).one()
    assert row[0] == [2] and row[1].startswith("Fixture") and row[2] == "resolved"


def test_recheck_window_is_counted_from_the_disputed_release(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed_two_question_script(client, published_written["chapter"], seed=304)
    assert _ask(client, learner, a["id"], [1]).status_code == 409  # nothing released yet
    assert (
        _mark(client, _staff(client, ["subject_reviewer"]), a["id"], "initial", _awards(q1=100, q2=100)).status_code
        == 200
    )
    with get_sessionmaker()() as db:
        db.execute(
            text("update written_score_version set created_at = created_at - interval '15 days' where attempt_id = :a"),
            {"a": a["id"]},
        )
        db.commit()
    state = _result(client, learner, a["id"])["recheck"]
    assert state["status"] == "closed" and state["closed_reason"] == "window_ended"
    late = _ask(client, learner, a["id"], [1])
    assert late.status_code == 409 and late.json()["code_reason"] == "WINDOW_ENDED"
