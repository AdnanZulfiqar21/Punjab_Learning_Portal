"""Learner actions on pending questions: rescans, classification, confirmed-unanswered and deadlines (W04.S3.T2,
W06.S2.T4, WA-AC62/63/82). Technical fixtures only: no mark or classification here is accuracy evidence."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from portal_api.modules.written import rescans
from tests.test_content_workflow import Staff
from tests.test_written_attempts import _learner, _map, _png, _seal, _start, _upload

SCOPE = {"grades": [12], "subjects": ["chemistry"]}


def _staff(client: TestClient) -> Staff:
    with get_sessionmaker()() as db:
        return Staff(client, db, ["subject_reviewer"], SCOPE)


def _aw(**units: int) -> dict[str, Any]:
    return {k[1:]: {"a1": {"units": v}, "b1": {"units": 0}, "b2": {"units": 0}} for k, v in units.items()}


def _sealed(client: TestClient, chapter: str, seed: int) -> tuple[Staff, dict[str, Any]]:
    learner = _learner(client)
    a = _start(client, learner, chapter, question_count=2)
    page = _upload(client, learner, a["id"], _png(seed=seed)).json()["pages"][0]["id"]
    m = _map(client, learner, a, {k: {"pages": [page]} for k in ("1:a", "1:b", "2:a", "2:b")}).json()
    assert _seal(client, learner, a["id"], m["manifest_revision"]).status_code == 200
    return learner, a


def _case(client: TestClient, who: Staff, attempt_id: str, kind: str) -> dict[str, Any]:
    return next(
        c
        for c in client.get("/v1/studio/written/queue", headers=who.headers).json()
        if c["reference"] == attempt_id[:8] and c["case_kind"] == kind
    )


def _decide(client: TestClient, who: Staff, attempt_id: str, kind: str, **body: Any) -> Any:
    case = _case(client, who, attempt_id, kind)
    v = client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=who.headers).json()["version"]
    return client.post(
        f"/v1/studio/written/cases/{case['id']}/decision",
        headers=who.headers,
        json={"expected_version": v, "release": True, **body},
    )


def _ask(action: str) -> dict[str, Any]:
    return {"2": {"status": "pending", "reason": "Fixture: answer 2 can't be read", "learner_action": action}}


def _result(client: TestClient, learner: Staff, attempt_id: str) -> Any:
    return client.get(f"/v1/written-attempts/{attempt_id}/result", headers=learner.headers).json()


def _rescan(client: TestClient, learner: Staff, attempt_id: str, seed: int, position: int = 2) -> Any:
    return client.post(
        f"/v1/written-attempts/{attempt_id}/questions/{position}/rescan",
        params={"note": "Fixture: clearer photo of the same page"},
        headers={**learner.headers, "Content-Type": "application/octet-stream"},
        content=_png(seed=seed),
    )


def _ledger(attempt_id: str) -> list[tuple[str, int | None]]:
    with get_sessionmaker()() as db:
        rows = db.execute(
            text("select kind, position from allowance_event where attempt_id = :a order by kind, position"),
            {"a": attempt_id},
        ).all()
    return [(k, p) for k, p in rows]


def test_a_readability_rescan_is_classified_and_assessed_without_a_second_charge(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=961)
    t = _staff(client)
    assert _decide(client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_ask("rescan")).status_code == 200
    q2 = _result(client, learner, a["id"])["questions"][1]
    assert q2["status"] == "pending" and q2["learner_action"] == "rescan" and q2["action_deadline"]

    r = _rescan(client, learner, a["id"], seed=962)
    assert r.status_code == 201, r.text
    case = _case(client, t, a["id"], "completion")
    detail = client.get(f"/v1/studio/written/cases/{case['id']}", headers=t.headers).json()
    rev = detail["revisions"][0]
    assert rev["position"] == 2 and rev["classification"] is None and rev["prior_page_ids"] and rev["pages"]
    seen = client.get(f"/v1/studio/written/cases/{case['id']}/pages/{rev['pages'][0]['id']}", headers=t.headers)
    assert seen.status_code == 200  # the marker sees the clearer copy beside the sealed original

    unclassified = _decide(client, t, a["id"], "completion", awards=_aw(q2=200))
    assert unclassified.status_code == 422 and unclassified.json()["code_reason"] == "REVISION_UNCLASSIFIED"
    ok = _decide(
        client,
        t,
        a["id"],
        "completion",
        awards=_aw(q2=200),
        classifications={rev["id"]: {"class": "READABILITY", "reason": "Fixture: same working, sharper photo"}},
    )
    assert ok.status_code == 200, ok.text
    final = _result(client, learner, a["id"])
    assert final["completeness"] == "complete" and [q["earned_units"] for q in final["questions"]] == [100, 200]
    assert final["questions"][1]["revisions"][0]["classification"] == "READABILITY"
    assert sorted(p for k, p in _ledger(a["id"]) if k == "CONSUMED") == [1, 2]  # once each, no second charge


def test_new_content_leaves_the_original_result_and_is_shown_to_the_learner(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=963)
    t = _staff(client)
    assert _decide(client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_ask("rescan")).status_code == 200
    assert _rescan(client, learner, a["id"], seed=964).status_code == 201
    rev_id = str(rescans.revisions_for(get_sessionmaker()(), uuid.UUID(a["id"]))[0].id)
    r = _decide(
        client,
        t,
        a["id"],
        "completion",
        awards={},
        question_status={"2": {"status": "unavailable", "reason": "Fixture: original unreadable; rescan is new work"}},
        classifications={rev_id: {"class": "NEW_CONTENT", "reason": "Fixture: working differs from the original"}},
    )
    assert r.status_code == 200, r.text
    q2 = _result(client, learner, a["id"])["questions"][1]
    assert q2["status"] == "unavailable" and q2["earned_units"] is None
    assert q2["revisions"][0]["classification"] == "NEW_CONTENT"


def test_a_confirmed_unanswered_question_resolves_like_a_declared_one(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=965)
    t = _staff(client)
    assert _decide(client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_ask("rescan")).status_code == 200
    url = f"/v1/written-attempts/{a['id']}/questions/2/confirm-unanswered"
    assert client.post(url, headers=learner.headers).status_code == 409  # only offered for blank-looking evidence

    learner2, b = _sealed(client, published_written["chapter"], seed=966)
    assert (
        _decide(
            client, t, b["id"], "initial", awards=_aw(q1=100), question_status=_ask("confirm_or_rescan")
        ).status_code
        == 200
    )
    url = f"/v1/written-attempts/{b['id']}/questions/2/confirm-unanswered"
    assert client.post(url, headers=learner.headers).status_code == 404  # someone else's script
    assert client.post(url, headers=learner2.headers).status_code == 204
    final = _result(client, learner2, b["id"])
    assert final["completeness"] == "complete" and final["questions"][1]["earned_units"] == 0
    assert ("RELEASED", 2) in _ledger(b["id"]) and ("CONSUMED", 2) not in _ledger(b["id"])
    with get_sessionmaker()() as db:
        open_cases = db.execute(
            text("select count(*) from written_review_case where attempt_id = :a and status = 'queued'"),
            {"a": b["id"]},
        ).scalar()
        method = db.execute(
            text("select decision_method from written_score_version where attempt_id = :a order by version desc"),
            {"a": b["id"]},
        ).first()[0]
    assert open_cases == 0 and method == "LEARNER"


def test_the_deadline_resolves_unanswered_requests_as_unavailable_without_a_zero(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=967)
    t = _staff(client)
    assert _decide(client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_ask("rescan")).status_code == 200
    with get_sessionmaker()() as db:
        db.execute(
            text(
                "update written_score_version set question_status = jsonb_set(question_status, '{2,action_deadline}', "
                "to_jsonb((clock_timestamp() - interval '1 hour')::text)) where attempt_id = :a"
            ),
            {"a": a["id"]},
        )
        db.commit()
    assert _rescan(client, learner, a["id"], seed=968).json()["code_reason"] == "ACTION_DEADLINE_PASSED"
    with get_sessionmaker()() as db:
        assert rescans.expire_learner_actions(db) >= 1
        assert rescans.expire_learner_actions(db) == 0  # idempotent
    q2 = _result(client, learner, a["id"])["questions"][1]
    assert q2["status"] == "unavailable" and q2["earned_units"] is None and "7 days" in q2["status_reason"]
    assert ("RELEASED", 2) in _ledger(a["id"])


def test_rescan_limits_ownership_and_a_fixed_deadline(client: TestClient, published_written: dict[str, Any]) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=969)
    t = _staff(client)
    assert _decide(client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_ask("rescan")).status_code == 200
    first_deadline = _result(client, learner, a["id"])["questions"][1]["action_deadline"]
    other = _learner(client)
    assert _rescan(client, other, a["id"], seed=970).status_code == 404
    same = _rescan(client, learner, a["id"], seed=969)  # the very file already sealed
    assert same.status_code == 409 and same.json()["code_reason"] == "SAME_FILE"
    assert _rescan(client, learner, a["id"], seed=971, position=1).json()["code_reason"] == "NO_LEARNER_ACTION"
    for seed in (972, 973, 974):
        assert _rescan(client, learner, a["id"], seed=seed).status_code == 201
    assert _rescan(client, learner, a["id"], seed=975).json()["code_reason"] == "RESCAN_LIMIT"
    # Re-asking the same action in the completion case keeps the original deadline.
    ids = [str(r.id) for r in rescans.revisions_for(get_sessionmaker()(), uuid.UUID(a["id"]))]
    r = _decide(
        client,
        t,
        a["id"],
        "completion",
        awards={},
        question_status=_ask("rescan"),
        classifications={i: {"class": "INDETERMINATE", "reason": "Fixture: still too blurred to compare"} for i in ids},
    )
    assert r.status_code == 200, r.text
    assert _result(client, learner, a["id"])["questions"][1]["action_deadline"] == first_deadline
