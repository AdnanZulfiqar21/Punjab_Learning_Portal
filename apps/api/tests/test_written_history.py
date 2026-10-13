"""W07.S2.T2 (HISTORY-01): the score history says what each version used and why marks changed.

Every released version lists, per question, its status and mark, the marking-guide version and the evidence (the
submitted original or a clearer copy the learner sent), whether it changed from the version before, and a plain
reason. Versions are labelled as a recheck, marking from a clearer copy, pending questions completed, a passed
deadline, or a marking-guide correction (covered with the regrade tests). Nothing is erased.

Technical fixtures only: the marks below verify software behaviour, not marking accuracy.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from portal_api.modules.written import rescans
from tests.test_recheck import _ask as _ask_recheck
from tests.test_recheck import _awards, _mark, _sealed_two_question_script
from tests.test_recheck import _staff as _recheck_staff
from tests.test_rescans import _ask, _aw, _case, _decide, _rescan, _result, _sealed, _staff


def _by_position(version: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {q["position"]: q for q in version["questions"]}


def test_a_recheck_is_explained_question_by_question(client: TestClient, published_written: dict[str, Any]) -> None:
    learner, a = _sealed_two_question_script(client, published_written["chapter"], seed=1401)
    first, second, third = (_recheck_staff(client, ["subject_reviewer"]) for _ in range(3))
    assert _mark(client, first, a["id"], "initial", _awards(q1=100, q2=100)).status_code == 200
    assert _ask_recheck(client, learner, a["id"], [1]).status_code == 200
    assert _mark(client, second, a["id"], "recheck", _awards(q1=200)).status_code == 200
    assert _ask_recheck(client, learner, a["id"], [1]).status_code == 200  # an appeal against the correction
    assert _mark(client, third, a["id"], "recheck", _awards(q1=200)).status_code == 200  # upheld

    v1, v2, v3 = _result(client, learner, a["id"])["versions"]
    assert (v1["labels"], v1["decision_method"], v1["case_kind"]) == ([], "TEACHER", "initial")
    for q in v1["questions"]:
        assert q["status"] == "scored" and q["evidence"] == "original" and q["rubric_version"] >= 1
        assert q["changed"] is False and q["reason"] is None  # the first marking needs no explanation

    assert v2["labels"] == ["recheck"]
    q1, q2 = _by_position(v2)[1], _by_position(v2)[2]
    assert (q1["earned_units"], q1["changed"]) == (200, True) and "after your recheck request" in q1["reason"]
    assert (q2["earned_units"], q2["changed"], q2["reason"]) == (100, False, None)  # carried forward, not asked
    assert q1["rubric_version"] == _by_position(v1)[1]["rubric_version"]  # the same marking guide

    q1 = _by_position(v3)[1]
    assert (q1["changed"], q1["reason"]) == (
        False,
        "Checked again by a different teacher after your recheck request; the mark stands.",
    )


def test_a_clearer_copy_and_a_passed_deadline_are_labelled(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    # A pending question marked from the clearer copy the learner sent.
    learner, a = _sealed(client, published_written["chapter"], seed=1402)
    t = _staff(client)
    assert _decide(client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_ask("rescan")).status_code == 200
    assert _rescan(client, learner, a["id"], seed=1403).status_code == 201
    detail = client.get(f"/v1/studio/written/cases/{_case(client, t, a['id'], 'completion')['id']}", headers=t.headers)
    rev = detail.json()["revisions"][0]["id"]
    done = _decide(
        client,
        t,
        a["id"],
        "completion",
        awards=_aw(q2=200),
        classifications={rev: {"class": "READABILITY", "reason": "Fixture: same working, sharper photo"}},
        evidence={"2": [rev]},
    )
    assert done.status_code == 200, done.text
    v1, v2 = _result(client, learner, a["id"])["versions"]
    assert _by_position(v1)[2]["status"] == "pending" and _by_position(v1)[2]["earned_units"] is None
    assert sorted(v2["labels"]) == ["clearer_copy", "pending_completed"]
    q2 = _by_position(v2)[2]
    assert (q2["status"], q2["earned_units"], q2["evidence"], q2["changed"]) == ("scored", 200, "clearer_copy", True)
    assert q2["reason"] == "Marked from the clearer copy you sent after it was pending."
    assert _by_position(v2)[1]["evidence"] == "original" and _by_position(v2)[1]["reason"] is None

    # A pending question whose deadline passed without a clearer copy.
    learner, b = _sealed(client, published_written["chapter"], seed=1404)
    assert _decide(client, t, b["id"], "initial", awards=_aw(q1=100), question_status=_ask("rescan")).status_code == 200
    with get_sessionmaker()() as db:
        db.execute(
            text(
                "update written_learner_obligation set deadline = clock_timestamp() - interval '1 hour' "
                "where attempt_id = :a"
            ),
            {"a": b["id"]},
        )
        db.commit()
    with get_sessionmaker()() as db:
        assert rescans.expire_learner_actions(db) >= 1
    versions = _result(client, learner, b["id"])["versions"]
    last = versions[-1]
    assert last["decision_method"] == "SYSTEM" and "deadline_passed" in last["labels"]
    q2 = _by_position(last)[2]
    assert (q2["status"], q2["earned_units"], q2["changed"]) == ("unavailable", None, True)
    assert "No clearer copy arrived by the deadline" in q2["reason"]
    assert [v["version"] for v in versions] == list(range(1, len(versions) + 1))  # nothing erased
