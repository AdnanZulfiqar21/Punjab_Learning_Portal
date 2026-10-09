"""P15.S3.T3: support staff find a learner by exact email (MFA), see a redacted activity timeline including trial
decisions, and can take explicit, time-limited, audited assisted access that the learner is told about and can end."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from portal_api.db import get_sessionmaker
from portal_api.modules.audit.models import AuditEvent
from tests.test_content_workflow import Staff


def _staff(client: TestClient, roles: list[str], mfa: bool = False) -> Staff:
    with get_sessionmaker()() as db:
        return Staff(client, db, roles, mfa=mfa)


def _ticket(client: TestClient, who: Staff) -> dict[str, Any]:
    r = client.post(
        "/v1/support/tickets",
        headers=who.headers,
        json={"category": "access", "subject": "Fixture: trial", "body": "Fixture: my trial will not start."},
    )
    assert r.status_code == 201, r.text
    return dict(r.json())


def _find(client: TestClient, who: Staff, email: str) -> Any:
    return client.post("/v1/staff/support/learners/lookup", headers=who.headers, json={"email": email})


def test_lookup_is_exact_mfa_only_audited_and_never_finds_staff(client: TestClient) -> None:
    learner = _staff(client, [])
    agent, no_mfa = _staff(client, ["support"], mfa=True), _staff(client, ["support"])
    assert _find(client, no_mfa, learner.email).status_code == 403
    assert _find(client, _staff(client, [], mfa=True), learner.email).status_code == 403  # learners can't look up
    found = _find(client, agent, f"  {learner.email.upper()} ")
    assert found.status_code == 200 and found.json()["id"] == str(learner.id)
    assert _find(client, agent, learner.email[:-4]).status_code == 404  # no partial matches
    assert _find(client, agent, no_mfa.email).status_code == 404  # staff accounts are out of scope
    with get_sessionmaker()() as db:
        rows = db.scalars(
            select(AuditEvent).where(AuditEvent.actor_user_id == agent.id, AuditEvent.action == "support.lookup")
        ).all()
    assert [r.details["found"] for r in rows].count(True) == 1 and len(rows) == 3
    assert all(learner.email not in str(r.details) for r in rows)  # the searched address is not stored


def test_timeline_is_redacted_and_includes_trial_decisions(client: TestClient) -> None:
    learner, agent = _staff(client, []), _staff(client, ["support"], mfa=True)
    assert client.post("/v1/me/trial", headers=learner.headers).status_code == 200
    t = _ticket(client, learner)
    _find(client, agent, learner.email)
    r = client.get(f"/v1/staff/support/learners/{learner.id}/timeline", headers=agent.headers)
    assert r.status_code == 200, r.text
    body = r.json()
    kinds = [e["kind"] for e in body["events"]]
    assert {"account.created", "trial.granted", "support.opened"} <= set(kinds)
    assert not any(k.startswith("account.support.") for k in kinds)  # staff lookups are not learner activity
    opened = next(e for e in body["events"] if e["kind"] == "support.opened")
    assert opened["detail"] == {"ticket_id": t["id"], "category": "access", "status": "open"}  # no message bodies
    assert "Fixture: my trial will not start." not in r.text
    assert body["assisted_access"] is None and body["learner"]["open_requests"] == 1
    assert r.headers["cache-control"] == "private, no-store"
    other = _staff(client, ["platform_operator"], mfa=True)
    assert client.get(f"/v1/staff/support/learners/{learner.id}/timeline", headers=other.headers).status_code == 403
    assert client.get(f"/v1/staff/support/learners/{agent.id}/timeline", headers=agent.headers).status_code == 404


def test_assisted_access_is_explicit_time_limited_told_and_endable(client: TestClient) -> None:
    learner, agent = _staff(client, []), _staff(client, ["support"], mfa=True)
    stranger = _staff(client, [])
    t, theirs = _ticket(client, learner), _ticket(client, stranger)
    url = f"/v1/staff/support/learners/{learner.id}/assisted-access"
    reason = "Fixture: checking why the trial did not start"
    assert client.post(url, headers=agent.headers, json={"ticket_id": t["id"], "reason": "short"}).status_code == 422
    too_long = {"ticket_id": t["id"], "reason": reason, "minutes": 31}
    assert client.post(url, headers=agent.headers, json=too_long).status_code == 422
    wrong = {"ticket_id": theirs["id"], "reason": reason}
    assert client.post(url, headers=agent.headers, json=wrong).status_code == 404  # another learner's request
    r = client.post(url, headers=agent.headers, json={"ticket_id": t["id"], "reason": reason, "minutes": 10})
    assert r.status_code == 201, r.text
    access = r.json()
    assert client.post(url, headers=agent.headers, json={"ticket_id": t["id"], "reason": reason}).status_code == 409
    timeline = client.get(f"/v1/staff/support/learners/{learner.id}/timeline", headers=agent.headers).json()
    assert timeline["assisted_access"]["id"] == access["id"]
    # the learner is told, can see it, and can end it
    events = [n["event"] for n in client.get("/v1/me/notifications", headers=learner.headers).json()["items"]]
    assert "support.assisted_access" in events
    mine = client.get("/v1/me/assisted-access", headers=learner.headers).json()
    assert [a["id"] for a in mine] == [access["id"]] and mine[0]["reason"] == reason
    assert client.delete(f"/v1/staff/support/assisted-access/{access['id']}", headers=stranger.headers).status_code in (
        403,
        404,
    )
    assert client.delete(f"/v1/me/assisted-access/{access['id']}", headers=stranger.headers).status_code == 404
    assert client.delete(f"/v1/me/assisted-access/{access['id']}", headers=learner.headers).status_code == 204
    assert client.delete(f"/v1/me/assisted-access/{access['id']}", headers=learner.headers).status_code == 409
    after = client.get(f"/v1/staff/support/learners/{learner.id}/timeline", headers=agent.headers).json()
    assert after["assisted_access"] is None
    with get_sessionmaker()() as db:
        actions = set(db.scalars(select(AuditEvent.action).where(AuditEvent.target_id == str(learner.id))).all())
    assert {"support.assisted_access_granted", "support.assisted_access_ended", "support.timeline_viewed"} <= actions
    # a resolved request can't be used
    staff = _staff(client, ["support"])
    client.post(
        f"/v1/staff/support/tickets/{t['id']}/messages",
        headers=staff.headers,
        json={"body": "Fixture: done.", "status": "resolved"},
    )
    assert client.post(url, headers=agent.headers, json={"ticket_id": t["id"], "reason": reason}).status_code == 409
