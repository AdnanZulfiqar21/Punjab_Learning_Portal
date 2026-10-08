"""Written result publication, pending work and appeals (review OCT8-02, OCT8-03, OCT8-04).

Two-question scripts, technical fixtures only. Races are driven with barriers/events on real PostgreSQL.
"""

from __future__ import annotations

import contextlib
import threading
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


def _sealed(client: TestClient, chapter: str, seed: int) -> tuple[Staff, dict[str, Any]]:
    learner = _learner(client)
    a = _start(client, learner, chapter, question_count=2)
    page = _upload(client, learner, a["id"], _png(seed=seed)).json()["pages"][0]["id"]
    m = _map(client, learner, a, {k: {"pages": [page]} for k in ("1:a", "1:b", "2:a", "2:b")}).json()
    assert _seal(client, learner, a["id"], m["manifest_revision"]).status_code == 200
    return learner, a


def _aw(**units: int) -> dict[str, Any]:
    return {k[1:]: {"a1": {"units": v}, "b1": {"units": 0}, "b2": {"units": 0}} for k, v in units.items()}


def _pending(*positions: int) -> dict[str, Any]:
    return {str(p): {"status": "pending", "reason": "Fixture: page unreadable"} for p in positions}


def _queued(client: TestClient, who: Staff, attempt_id: str, kind: str) -> list[dict[str, Any]]:
    return [
        c
        for c in client.get("/v1/studio/written/queue", headers=who.headers).json()
        if c["reference"] == attempt_id[:8] and c["case_kind"] == kind
    ]


def _lease(client: TestClient, who: Staff, case_id: str) -> Any:
    r = client.post(f"/v1/studio/written/cases/{case_id}/lease", headers=who.headers)
    assert r.status_code == 200, r.text
    return r.json()


def _decide(client: TestClient, who: Staff, case_id: str, version: int, **body: Any) -> Any:
    return client.post(
        f"/v1/studio/written/cases/{case_id}/decision",
        headers=who.headers,
        json={"expected_version": version, "release": True, **body},
    )


def _mark(client: TestClient, who: Staff, attempt_id: str, kind: str, **body: Any) -> Any:
    case = _queued(client, who, attempt_id, kind)[0]
    leased = _lease(client, who, case["id"])
    return _decide(client, who, case["id"], leased["version"], **body)


def _result(client: TestClient, learner: Staff, attempt_id: str) -> Any:
    return client.get(f"/v1/written-attempts/{attempt_id}/result", headers=learner.headers).json()


def _completion_positions(attempt_id: str) -> list[list[int]]:
    with get_sessionmaker()() as db:
        rows = db.execute(
            text(
                "select positions from written_review_case where attempt_id = :a and case_kind = 'completion' "
                "and status = 'queued' order by opened_at"
            ),
            {"a": attempt_id},
        ).all()
    return [sorted(r[0]) for r in rows]


# ------------------------------------------------------------------ OCT8-02
def test_partial_completion_keeps_one_case_for_the_remaining_pending_question(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=901)
    t = _staff(client, ["subject_reviewer"])
    assert _mark(client, t, a["id"], "initial", awards={}, question_status=_pending(1, 2)).status_code == 200
    assert _completion_positions(a["id"]) == [[1, 2]]
    with get_sessionmaker()() as db:
        first_due = db.execute(
            text("select due_at from written_review_case where attempt_id = :a and case_kind = 'completion'"),
            {"a": a["id"]},
        ).scalar()
    # Resolve Q1 only: Q2 must keep exactly one actionable case, with the original due time.
    r = _mark(client, t, a["id"], "completion", awards=_aw(q1=100), question_status=_pending(2))
    assert r.status_code == 200, r.text
    assert _completion_positions(a["id"]) == [[2]]
    with get_sessionmaker()() as db:
        due = db.execute(
            text(
                "select due_at from written_review_case where attempt_id = :a and case_kind = 'completion' "
                "and status = 'queued'"
            ),
            {"a": a["id"]},
        ).scalar()
    assert due == first_due  # the service obligation is not reset by partial progress
    # A no-progress completion still leaves exactly one case.
    assert _mark(client, t, a["id"], "completion", awards={}, question_status=_pending(2)).status_code == 200
    assert _completion_positions(a["id"]) == [[2]]
    # Finishing leaves no pending case behind.
    assert _mark(client, t, a["id"], "completion", awards=_aw(q2=200)).status_code == 200
    assert _completion_positions(a["id"]) == []
    assert _result(client, learner, a["id"])["completeness"] == "complete"


# ------------------------------------------------------------------ OCT8-03
def test_a_completion_release_does_not_strand_an_open_recheck(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=902)
    first, second = _staff(client, ["subject_reviewer"]), _staff(client, ["subject_reviewer"])
    assert _mark(client, first, a["id"], "initial", awards=_aw(q1=100), question_status=_pending(2)).status_code == 200
    ask = client.post(
        f"/v1/written-attempts/{a['id']}/recheck",
        headers=learner.headers,
        json={"reason": "Fixture: please look at question 1 again", "positions": [1]},
    )
    assert ask.status_code == 200
    assert _mark(client, first, a["id"], "completion", awards=_aw(q2=200)).status_code == 200  # V2 scores Q2
    # The recheck (pinned to V1) is rebased because only Q2, outside its scope, changed.
    r = _mark(client, second, a["id"], "recheck", awards=_aw(q1=200))
    assert r.status_code == 200, r.text
    final = _result(client, learner, a["id"])
    assert [q["earned_units"] for q in final["questions"]] == [200, 200]  # Q2's completion score is kept
    with get_sessionmaker()() as db:
        row = db.execute(
            text("select status, jsonb_array_length(rebases) from written_recheck_request where attempt_id = :a"),
            {"a": a["id"]},
        ).one()
    assert row == ("resolved", 1)  # the rebase is recorded


def test_concurrent_completion_and_recheck_publications_lose_nothing(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    from portal_api.modules.written import review

    learner, a = _sealed(client, published_written["chapter"], seed=903)
    first, second = _staff(client, ["subject_reviewer"]), _staff(client, ["subject_reviewer"])
    assert _mark(client, first, a["id"], "initial", awards=_aw(q1=100), question_status=_pending(2)).status_code == 200
    assert (
        client.post(
            f"/v1/written-attempts/{a['id']}/recheck",
            headers=learner.headers,
            json={"reason": "Fixture: please look at question 1 again", "positions": [1]},
        ).status_code
        == 200
    )
    completion = _queued(client, first, a["id"], "completion")[0]
    recheck = _queued(client, second, a["id"], "recheck")[0]
    cv = _lease(client, first, completion["id"])["version"]
    rv = _lease(client, second, recheck["id"])["version"]

    # Both decisions read the old result, then publish at the same moment.
    barrier = threading.Barrier(2)
    real = review.released_result

    def synced(db: Any, attempt_id: Any) -> Any:
        out = real(db, attempt_id)
        with contextlib.suppress(threading.BrokenBarrierError):  # the second caller may already be serialised
            barrier.wait(timeout=2)
        return out

    review.released_result = synced  # type: ignore[assignment]
    try:
        results: dict[str, int] = {}

        def go(name: str, who: Staff, case_id: str, version: int, awards: dict[str, Any]) -> None:
            results[name] = _decide(client, who, case_id, version, awards=awards).status_code

        threads = [
            threading.Thread(target=go, args=("completion", first, completion["id"], cv, _aw(q2=200))),
            threading.Thread(target=go, args=("recheck", second, recheck["id"], rv, _aw(q1=200))),
        ]
        for th in threads:
            th.start()
        for th in threads:
            th.join(60)
    finally:
        review.released_result = real  # type: ignore[assignment]
    assert results == {"completion": 200, "recheck": 200}, results
    final = _result(client, learner, a["id"])
    assert [q["earned_units"] for q in final["questions"]] == [200, 200]  # neither award was reverted
    with get_sessionmaker()() as db:
        consumed = db.execute(
            text(
                "select position, count(*) from allowance_event where attempt_id = :a and kind = 'CONSUMED' "
                "group by position order by position"
            ),
            {"a": a["id"]},
        ).all()
    assert [tuple(r) for r in consumed] == [(1, 1), (2, 1)]  # each question consumed exactly once


def test_an_adjudicator_expansion_into_a_pending_question_supersedes_its_completion_case(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=904)
    first = _staff(client, ["subject_reviewer"])
    adjudicator = _staff(client, ["academic_adjudicator"])
    assert _mark(client, first, a["id"], "initial", awards=_aw(q1=100), question_status=_pending(2)).status_code == 200
    assert (
        client.post(
            f"/v1/written-attempts/{a['id']}/recheck",
            headers=learner.headers,
            json={"reason": "Fixture: please look at question 1 again", "positions": [1]},
        ).status_code
        == 200
    )
    r = _mark(
        client,
        adjudicator,
        a["id"],
        "recheck",
        awards=_aw(q1=100, q2=200),
        expand_positions=[2],
        expansion_reason="Fixture: question 2 is readable on the second page",
    )
    assert r.status_code == 200, r.text
    assert _completion_positions(a["id"]) == []  # nothing pending remains, so the old case closed
    assert [q["earned_units"] for q in _result(client, learner, a["id"])["questions"]] == [100, 200]


def test_a_stale_lease_gets_a_recoverable_conflict(client: TestClient, published_written: dict[str, Any]) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=905)
    first, second = _staff(client, ["subject_reviewer"]), _staff(client, ["academic_adjudicator"])
    assert _mark(client, first, a["id"], "initial", awards=_aw(q1=100), question_status=_pending(2)).status_code == 200
    assert (
        client.post(
            f"/v1/written-attempts/{a['id']}/recheck",
            headers=learner.headers,
            json={"reason": "Fixture: please look at question 1 again", "positions": [1]},
        ).status_code
        == 200
    )
    completion = _queued(client, first, a["id"], "completion")[0]
    cv = _lease(client, first, completion["id"])["version"]  # sees Q2 pending
    # Meanwhile an adjudicator's widened recheck resolves Q2.
    assert (
        _mark(
            client,
            second,
            a["id"],
            "recheck",
            awards=_aw(q1=100, q2=100),
            expand_positions=[2],
            expansion_reason="Fixture: question 2 is readable on the second page",
        ).status_code
        == 200
    )
    stale = _decide(client, first, completion["id"], cv, awards=_aw(q2=200))
    assert stale.status_code in (404, 409)  # closed or stale: never a silent revert of Q2
    assert [q["earned_units"] for q in _result(client, learner, a["id"])["questions"]] == [100, 100]


# ------------------------------------------------------------------ OCT8-04
def test_completion_keeps_unused_appeals_and_newly_scored_questions_get_theirs(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=906)
    t = _staff(client, ["subject_reviewer"])
    assert _mark(client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_pending(2)).status_code == 200
    assert _result(client, learner, a["id"])["recheck"]["eligible_positions"] == [1]
    assert _mark(client, t, a["id"], "completion", awards=_aw(q2=200)).status_code == 200
    state = _result(client, learner, a["id"])["recheck"]
    assert state["eligible_positions"] == [1, 2]  # Q1's unused appeal survives; Q2 gets its first one
    windows = state["windows"]
    assert windows["1"] < windows["2"]  # Q1's window is not restarted by the completion
    # Using Q1's appeal, upheld unchanged, leaves Q2 still open and Q1 closed.
    assert (
        client.post(
            f"/v1/written-attempts/{a['id']}/recheck",
            headers=learner.headers,
            json={"reason": "Fixture: please look at question 1 again", "positions": [1]},
        ).status_code
        == 200
    )
    assert (
        _mark(client, _staff(client, ["subject_reviewer"]), a["id"], "recheck", awards=_aw(q1=100)).status_code == 200
    )
    assert _result(client, learner, a["id"])["recheck"]["eligible_positions"] == [2]
