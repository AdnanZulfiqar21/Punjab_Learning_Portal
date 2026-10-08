"""Per-question outcomes, allowance allocations, remedies and funded review capacity (review R05; §20.9.3, §20.10,
§20.13.3/4, W08). Technical fixtures only: no marks here are evidence of marking accuracy."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from tests.test_content_workflow import Staff
from tests.test_written_attempts import _form, _learner, _map, _png, _seal, _start, _upload

SCOPE = {"grades": [12], "subjects": ["chemistry"]}


def _staff(client: TestClient, roles: list[str], mfa: bool = False) -> Staff:
    with get_sessionmaker()() as db:
        return Staff(client, db, roles, SCOPE if roles != ["finance"] and roles != ["platform_operator"] else None, mfa)


def _sealed(client: TestClient, chapter: str, seed: int, answer_q2: bool = True) -> tuple[Staff, dict[str, Any]]:
    learner = _learner(client)
    a = _start(client, learner, chapter, question_count=2)
    page = _upload(client, learner, a["id"], _png(seed=seed)).json()["pages"][0]["id"]
    slots: dict[str, Any] = {"1:a": {"pages": [page]}, "1:b": {"pages": [page]}}
    slots |= (
        {"2:a": {"pages": [page]}, "2:b": {"pages": [page]}}
        if answer_q2
        else {
            "2:a": {"unanswered": True},
            "2:b": {"unanswered": True},
        }
    )
    m = _map(client, learner, a, slots).json()
    assert _seal(client, learner, a["id"], m["manifest_revision"]).status_code == 200
    return learner, a


def _awards(**units: int) -> dict[str, Any]:
    return {k[1:]: {"a1": {"units": v}, "b1": {"units": 0}, "b2": {"units": 0}} for k, v in units.items()}


def _decide(client: TestClient, who: Staff, attempt_id: str, kind: str, body: dict[str, Any]) -> Any:
    case = next(
        c
        for c in client.get("/v1/studio/written/queue", headers=who.headers).json()
        if c["reference"] == attempt_id[:8] and c["case_kind"] == kind
    )
    lease = client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=who.headers)
    assert lease.status_code == 200, lease.text
    return client.post(
        f"/v1/studio/written/cases/{case['id']}/decision",
        headers=who.headers,
        json={"expected_version": lease.json()["version"], "release": True, **body},
    )


def _ledger(attempt_id: str) -> list[tuple[str, int | None, int]]:
    with get_sessionmaker()() as db:
        rows = db.execute(
            text("select kind, position, units from allowance_event where attempt_id = :a order by kind, position"),
            {"a": attempt_id},
        ).all()
    return [(k, p, u) for k, p, u in rows]


def _allowance(client: TestClient, learner: Staff) -> dict[str, int]:
    return dict(client.get("/v1/me/access", headers=learner.headers).json()["written_allowance"])


def test_only_answered_questions_are_accepted(client: TestClient, published_written: dict[str, Any]) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=501, answer_q2=False)
    accepted = [(p, u) for k, p, u in _ledger(a["id"]) if k == "ACCEPTED"]
    assert accepted == [(1, 1)]  # question 2 was declared unanswered: nothing accepted for it
    assert _allowance(client, learner)["accepted"] == 1


def test_pending_questions_are_not_scored_and_complete_later(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=502)
    teacher = _staff(client, ["subject_reviewer"])
    no_reason = _decide(
        client,
        teacher,
        a["id"],
        "initial",
        {
            "awards": _awards(q1=100),
            "question_status": {"2": {"status": "pending"}},
        },
    )
    assert no_reason.status_code == 422
    with_award = _decide(
        client,
        teacher,
        a["id"],
        "initial",
        {
            "awards": _awards(q1=100, q2=0),
            "question_status": {"2": {"status": "pending", "reason": "Fixture: unreadable"}},
        },
    )
    assert with_award.status_code == 422  # no invented zero for unassessed work
    ok = _decide(
        client,
        teacher,
        a["id"],
        "initial",
        {
            "awards": _awards(q1=100),
            "question_status": {"2": {"status": "pending", "reason": "Fixture: page too blurred to read"}},
        },
    )
    assert ok.status_code == 200, ok.text

    result = client.get(f"/v1/written-attempts/{a['id']}/result", headers=learner.headers).json()
    assert result["completeness"] == "partial_pending" and result["scored_max_units"] == 500
    q1, q2 = result["questions"]
    assert q1["status"] == "scored" and q1["earned_units"] == 100
    assert q2["status"] == "pending" and q2["earned_units"] is None and q2["criteria"] == []
    assert "blurred" in q2["status_reason"]
    assert result["recheck"]["eligible_positions"] == [1]  # nothing to dispute on a pending question
    assert ("CONSUMED", 1, 1) in _ledger(a["id"]) and not any(
        k == "CONSUMED" and p == 2 for k, p, _ in _ledger(a["id"])
    )

    # A completion case marks only question 2; question 1 is carried forward exactly.
    case = next(
        c
        for c in client.get("/v1/studio/written/queue", headers=teacher.headers).json()
        if c["reference"] == a["id"][:8] and c["case_kind"] == "completion"
    )
    assert case["due_at"] is not None
    detail = client.get(f"/v1/studio/written/cases/{case['id']}", headers=teacher.headers).json()
    assert detail["completion"]["positions"] == [2] and detail["completion"]["carried_forward"] == {"1": 100}
    outside = _decide(client, teacher, a["id"], "completion", {"awards": _awards(q1=200, q2=100)})
    assert outside.status_code == 422
    done = _decide(client, teacher, a["id"], "completion", {"awards": _awards(q2=200)})
    assert done.status_code == 200, done.text
    final = client.get(f"/v1/written-attempts/{a['id']}/result", headers=learner.headers).json()
    assert final["completeness"] == "complete" and final["total_units"] == 300
    assert [q["earned_units"] for q in final["questions"]] == [100, 200]
    consumed = sorted(p for k, p, _ in _ledger(a["id"]) if k == "CONSUMED")
    assert consumed == [1, 2]  # each question consumed exactly once


def test_unavailable_questions_return_their_allowance(client: TestClient, published_written: dict[str, Any]) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=503)
    before = _allowance(client, learner)
    r = _decide(
        client,
        _staff(client, ["subject_reviewer"]),
        a["id"],
        "initial",
        {
            "awards": _awards(q1=200),
            "question_status": {"2": {"status": "unavailable", "reason": "Fixture: no teacher for this notation"}},
        },
    )
    assert r.status_code == 200, r.text
    result = client.get(f"/v1/written-attempts/{a['id']}/result", headers=learner.headers).json()
    assert result["completeness"] == "partial_unavailable" and result["questions"][1]["earned_units"] is None
    after = _allowance(client, learner)
    assert ("RELEASED", 2, 1) in _ledger(a["id"]) and ("CONSUMED", 1, 1) in _ledger(a["id"])
    assert after["available"] == before["available"] + 1 and after["consumed"] == before["consumed"] + 1
    assert not any(
        c["case_kind"] == "completion" and c["reference"] == a["id"][:8]
        for c in client.get("/v1/studio/written/queue", headers=_staff(client, ["subject_reviewer"]).headers).json()
    )


def test_rechecks_cannot_mark_questions_pending(client: TestClient, published_written: dict[str, Any]) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=504)
    assert (
        _decide(
            client, _staff(client, ["subject_reviewer"]), a["id"], "initial", {"awards": _awards(q1=100, q2=100)}
        ).status_code
        == 200
    )
    ask = client.post(
        f"/v1/written-attempts/{a['id']}/recheck",
        headers=learner.headers,
        json={"reason": "Fixture: please look again", "positions": [1]},
    )
    assert ask.status_code == 200
    r = _decide(
        client,
        _staff(client, ["subject_reviewer"]),
        a["id"],
        "recheck",
        {
            "awards": {},
            "question_status": {"1": {"status": "pending", "reason": "Fixture: trying to defer"}},
        },
    )
    assert r.status_code == 422


def test_remedy_credits_are_separate_idempotent_and_authorised(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=505)
    body = {
        "attempt_id": a["id"],
        "position": 1,
        "units": 2,
        "reason": "Fixture: service defect remedy",
        "defect_ref": "FIXTURE-INC-1",
        "idempotency_key": uuid.uuid4().hex,
    }
    assert (
        client.post(
            "/v1/staff/written-remedies", headers=_staff(client, ["subject_reviewer"]).headers, json=body
        ).status_code
        == 403
    )
    finance = _staff(client, ["finance"], mfa=True)
    before = _allowance(client, learner)["available"]
    first = client.post("/v1/staff/written-remedies", headers=finance.headers, json=body)
    assert first.status_code == 200, first.text
    again = client.post("/v1/staff/written-remedies", headers=finance.headers, json=body)
    assert again.json()["id"] == first.json()["id"]  # a retry returns the original credit
    clash = client.post("/v1/staff/written-remedies", headers=finance.headers, json={**body, "units": 3})
    assert clash.status_code == 409
    assert _allowance(client, learner)["available"] == before + 2
    assert sum(1 for k, _, _ in _ledger(a["id"]) if k == "REMEDY_CREDIT") == 1


def test_new_written_starts_need_funded_capacity_but_accepted_work_continues(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    operator = _staff(client, ["platform_operator"], mfa=True)
    chapter = published_written["chapter"]
    assert (
        client.put(
            "/v1/ops/written-capacity/12/chemistry",
            headers=_staff(client, ["subject_reviewer"]).headers,
            json={"max_open_cases": 5, "reason": "Fixture capacity"},
        ).status_code
        == 403
    )
    backlog = client.get("/v1/ops/written-backlog", headers=operator.headers).json()
    row = next(r for r in backlog if r["grade"] == 12 and r["subject"] == "chemistry")
    load = row["open_cases"] + row["open_permits"]
    try:
        # Exactly one more start fits.
        r = client.put(
            "/v1/ops/written-capacity/12/chemistry",
            headers=operator.headers,
            json={"max_open_cases": load + 1, "reason": "Fixture: one place left"},
        )
        assert r.status_code == 200 and r.json()["accepting"]
        first = _learner(client)
        _start(client, first, chapter)
        second = _learner(client)
        f = _form(client, second, chapter)
        refused = client.post(f"/v1/written/forms/{f.json()['id']}/attempt", headers=second.headers)
        assert refused.status_code == 409 and refused.json()["code_reason"] == "REVIEW_AT_CAPACITY"
        av = client.get("/v1/written/availability?grade=12&subject=chemistry", headers=second.headers).json()
        assert av["review_staffed"] and not av["review_accepting"]
    finally:
        client.put(
            "/v1/ops/written-capacity/12/chemistry",
            headers=operator.headers,
            json={"max_open_cases": 10_000, "reason": "Fixture: restore"},
        )
