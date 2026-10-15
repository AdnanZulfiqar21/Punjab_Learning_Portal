"""W07.S1.T2 (FEEDBACK-COPIES-01): feedback can point at a place on the clearer copy a question was marked from, and
the learner sees it as a place on that copy; a copy not used for the marking can't be pointed at. Technical fixtures
only."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.test_rescans import _ask, _aw, _case, _decide, _rescan, _result, _sealed, _staff


def test_feedback_points_at_the_clearer_copy_the_answer_was_marked_from(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=981)
    t = _staff(client)
    assert _decide(client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_ask("rescan")).status_code == 200
    assert _rescan(client, learner, a["id"], seed=982).status_code == 201
    case = _case(client, t, a["id"], "completion")
    rev = client.get(f"/v1/studio/written/cases/{case['id']}", headers=t.headers).json()["revisions"][0]
    copy_page = rev["pages"][0]["id"]
    readable = {rev["id"]: {"class": "READABILITY", "reason": "Fixture: same working, sharper photo"}}

    def awards_on(page: str) -> dict[str, Any]:
        aw = _aw(q2=200)
        aw["2"]["a1"]["evidence"] = [{"page_id": page, "region": [0.0, 0.5, 0.5, 0.5]}]
        aw["2"]["a1"]["reason"] = "Fixture: the working is shown here"
        return aw

    unnamed = _decide(client, t, a["id"], "completion", awards=awards_on(copy_page), classifications=readable)
    assert unnamed.status_code == 422  # the copy wasn't named as this answer's evidence, so it can't be pointed at
    assert any("evidence must point to a page" in e for e in unnamed.json()["errors"])

    ok = _decide(
        client,
        t,
        a["id"],
        "completion",
        awards=awards_on(copy_page),
        classifications=readable,
        evidence={"2": [rev["id"]]},
    )
    assert ok.status_code == 200, ok.text
    [place] = next(c for c in _result(client, learner, a["id"])["questions"][1]["criteria"] if c["id"] == "a1")[
        "evidence"
    ]
    assert place["clearer_copy"] is True and place["page_number"] == 1 and place["available"] is True
    assert place["where"] == "your clearer copy for question 2, page 1, bottom left"
    assert place["region"] == [0.0, 0.5, 0.5, 0.5]
    shown = client.get(f"/v1/written-attempts/{a['id']}/pages/{copy_page}", headers=learner.headers)
    assert shown.status_code == 200 and shown.headers["content-type"] == "image/png"  # the learner can open it
