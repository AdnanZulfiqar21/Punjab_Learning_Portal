"""Support tickets, academic reports and written rechecks (P15.S3, W06.S2.T1). Fixture accounts and content only."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from portal_api.db import get_sessionmaker
from tests.test_content_workflow import Staff
from tests.test_written_attempts import _learner, _start


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
