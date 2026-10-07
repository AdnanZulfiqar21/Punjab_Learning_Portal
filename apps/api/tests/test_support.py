"""Support tickets, academic reports and written rechecks (P15.S3, W06.S2.T1). Fixture accounts and content only."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from tests.test_content_workflow import Staff
from tests.test_written_attempts import _learner, _map, _png, _seal, _start, _upload


def _staff(client: TestClient, roles: list[str], scope: dict[str, Any] | None = None) -> Staff:
    with get_sessionmaker()() as db:
        return Staff(client, db, roles, scope)


def _ticket(client: TestClient, who: Staff, **body: Any) -> Any:
    payload = {
        "category": "technical",
        "subject": "Fixture problem",
        "body": "Fixture description of the problem.",
        **body,
    }
    return client.post("/v1/support/tickets", headers=who.headers, json=payload)


def test_learners_own_their_tickets(client: TestClient) -> None:
    learner, other = _learner(client), _learner(client)
    t = _ticket(client, learner)
    assert t.status_code == 201 and t.json()["status"] == "open" and len(t.json()["messages"]) == 1
    assert client.get(f"/v1/support/tickets/{t.json()['id']}", headers=other.headers).status_code == 404
    reply = client.post(
        f"/v1/support/tickets/{t.json()['id']}/messages", headers=learner.headers, json={"body": "More detail"}
    )
    assert len(reply.json()["messages"]) == 2
    foreign = _ticket(client, learner, reference={"kind": "written_attempt", "id": str(uuid.uuid4())})
    assert foreign.status_code == 404
    no_question = _ticket(client, learner, category="academic_report")
    assert no_question.status_code == 422


def test_open_ticket_limit(client: TestClient) -> None:
    learner = _learner(client)
    for _ in range(5):
        assert _ticket(client, learner).status_code == 201
    assert _ticket(client, learner).status_code == 409


def test_academic_reports_route_to_scoped_reviewers_without_learner_identity(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner = _learner(client)
    a = _start(client, learner, published_written["chapter"])
    report = _ticket(
        client,
        learner,
        category="academic_report",
        subject="Question 1 looks wrong",
        reference={"kind": "written_attempt", "id": a["id"], "position": 1},
    )
    assert report.status_code == 201
    assert "content_item_id" not in report.json() and "rubric" not in str(report.json()).lower()
    tid = report.json()["id"]
    reviewer = _staff(client, ["subject_reviewer"], {"grades": [12], "subjects": ["chemistry"]})
    outsider = _staff(client, ["subject_reviewer"], {"grades": [11], "subjects": ["physics"]})
    support = _staff(client, ["support"])
    assert tid in [t["id"] for t in client.get("/v1/staff/support/tickets", headers=reviewer.headers).json()]
    assert tid not in [t["id"] for t in client.get("/v1/staff/support/tickets", headers=outsider.headers).json()]
    assert client.get(f"/v1/staff/support/tickets/{tid}", headers=outsider.headers).status_code == 404
    seen = client.get(f"/v1/staff/support/tickets/{tid}", headers=reviewer.headers).json()
    assert seen["context"]["learner"] is None and seen["context"]["question"]["kind"] == "written"
    assert learner.email not in str(seen)
    by_support = client.get(f"/v1/staff/support/tickets/{tid}", headers=support.headers).json()
    assert by_support["context"]["learner"]["email"] == learner.email and by_support["context"]["plan"]["has_access"]

    client.post(
        f"/v1/staff/support/tickets/{tid}/messages",
        headers=reviewer.headers,
        json={"body": "Internal: checking against the source page", "internal": True},
    )
    answered = client.post(
        f"/v1/staff/support/tickets/{tid}/messages",
        headers=reviewer.headers,
        json={"body": "Thanks, we're reviewing this question."},
    )
    assert answered.json()["status"] == "waiting_learner"
    mine = client.get(f"/v1/support/tickets/{tid}", headers=learner.headers).json()
    bodies = [m["body"] for m in mine["messages"]]
    assert "Thanks, we're reviewing this question." in bodies and not any("Internal" in b for b in bodies)
    learner_only = _learner(client)
    assert client.get("/v1/staff/support/tickets", headers=learner_only.headers).status_code == 403


def test_recheck_opens_a_new_case_and_never_charges_twice(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner = _learner(client)
    a = _start(client, learner, published_written["chapter"])
    page = _upload(client, learner, a["id"], _png(seed=77)).json()["page"]["id"]
    m = _map(client, learner, a, {"1:a": {"pages": [page]}, "1:b": {"pages": [page]}}).json()
    assert _seal(client, learner, a["id"], m["manifest_revision"]).status_code == 200
    reviewer = _staff(client, ["subject_reviewer"], {"grades": [12], "subjects": ["chemistry"]})
    second = _staff(client, ["subject_reviewer"], {"grades": [12], "subjects": ["chemistry"]})

    def mark(units_a: int, version: int, kind: str, who: Any = reviewer) -> None:
        case = next(
            c
            for c in client.get("/v1/studio/written/queue", headers=who.headers).json()
            if c["reference"] == a["id"][:8] and c["case_kind"] == kind
        )
        leased = client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=who.headers)
        assert leased.status_code == 200, leased.text
        r = client.post(
            f"/v1/studio/written/cases/{case['id']}/decision",
            headers=who.headers,
            json={
                "expected_version": 0,
                "release": True,
                "awards": {"1": {"a1": {"units": units_a}, "b1": {"units": 0}, "b2": {"units": 0}}},
            },
        )
        assert r.status_code == 200, r.text

    early = client.post(
        f"/v1/written-attempts/{a['id']}/recheck",
        headers=learner.headers,
        json={"reason": "Fixture: please look again", "positions": [1]},
    )
    assert early.status_code == 409  # no released result yet
    mark(100, 0, "initial")
    result = client.get(f"/v1/written-attempts/{a['id']}/result", headers=learner.headers).json()
    assert result["recheck"]["status"] == "available" and result["total_units"] == 100
    consumed_before = client.get("/v1/me/access", headers=learner.headers).json()["written_allowance"]["consumed"]

    req = client.post(
        f"/v1/written-attempts/{a['id']}/recheck",
        headers=learner.headers,
        json={"reason": "Fixture: part (a) has more working on the page", "positions": [1]},
    )
    assert req.status_code == 200 and req.json()["status"] == "requested"
    again = client.post(
        f"/v1/written-attempts/{a['id']}/recheck",
        headers=learner.headers,
        json={"reason": "Fixture: asking twice", "positions": [1]},
    )
    assert again.status_code == 409
    recheck_case = next(
        c
        for c in client.get("/v1/studio/written/queue", headers=reviewer.headers).json()
        if c["reference"] == a["id"][:8] and c["case_kind"] == "recheck"
    )
    own = client.post(f"/v1/studio/written/cases/{recheck_case['id']}/lease", headers=reviewer.headers)
    assert own.status_code == 403  # the original marker can't recheck their own marking
    mark(200, 0, "recheck", second)
    after = client.get(f"/v1/written-attempts/{a['id']}/result", headers=learner.headers).json()
    assert after["total_units"] == 200 and [h["case_kind"] for h in after["history"]] == ["initial", "recheck"]
    assert after["history"][0]["total_units"] == 100  # the original result is preserved
    access = client.get("/v1/me/access", headers=learner.headers).json()["written_allowance"]
    assert access["consumed"] == consumed_before  # a recheck of the same work consumes nothing extra

    with get_sessionmaker()() as db:
        db.execute(
            text("update written_score_version set created_at = created_at - interval '15 days' where attempt_id = :a"),
            {"a": a["id"]},
        )
        db.commit()
    closed = client.get(f"/v1/written-attempts/{a['id']}/result", headers=learner.headers).json()
    assert closed["recheck"]["status"] == "closed"
