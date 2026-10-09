"""P15.S4.T3: automated rehearsals of the common incidents in `docs/runbooks/`. Each walks the documented staff tools
end to end (never manual database edits) and checks the audit trail. Accounts and requests are technical fixtures."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from portal_api.db import get_sessionmaker
from portal_api.modules.audit.models import AuditEvent
from tests.test_content_workflow import Staff


def _staff(client: TestClient, roles: list[str], mfa: bool = False) -> Staff:
    with get_sessionmaker()() as db:
        return Staff(client, db, roles, mfa=mfa)


def _request(client: TestClient, who: Staff, subject: str, body: str) -> dict[str, Any]:
    r = client.post(
        "/v1/support/tickets", headers=who.headers, json={"category": "access", "subject": subject, "body": body}
    )
    assert r.status_code == 201, r.text
    return dict(r.json())


def _kinds(client: TestClient, agent: Staff, user_id: uuid.UUID) -> list[dict[str, Any]]:
    r = client.get(f"/v1/staff/support/learners/{user_id}/timeline", headers=agent.headers)
    assert r.status_code == 200, r.text
    return list(r.json()["events"])


def _audited(target_id: str) -> set[str]:
    with get_sessionmaker()() as db:
        return set(db.scalars(select(AuditEvent.action).where(AuditEvent.target_id == target_id)).all())


def test_rehearsal_missing_paid_access(client: TestClient) -> None:
    """Runbook `missing-access.md`: a learner says they paid but have no access. Payments are not live (B06), so the
    documented remedy is a time-limited promotional grant by finance with a reason that cites the request."""
    learner = _staff(client, [])
    ticket = _request(
        client, learner, "Fixture: paid but no access", "Fixture: I paid yesterday but cannot open tests."
    )
    agent, finance = _staff(client, ["support"], mfa=True), _staff(client, ["finance"], mfa=True)
    # 1. Support verifies identity and current access from the timeline (no payment record exists yet).
    found = client.post("/v1/staff/support/learners/lookup", headers=agent.headers, json={"email": learner.email})
    assert found.status_code == 200
    assert not any(e["kind"] == "access.granted" for e in _kinds(client, agent, learner.id))
    # 2. Support escalates to finance with the evidence; finance grants interim access citing the request.
    esc = client.post(
        f"/v1/staff/support/tickets/{ticket['id']}/escalate",
        headers=agent.headers,
        json={"reason": "Fixture: payment evidence attached; finance to grant interim access"},
    )
    assert esc.status_code == 200
    grant = client.post(
        "/v1/admin/entitlements",
        headers=finance.headers,
        json={
            "email": learner.email,
            "source": "promotional",
            "days": 7,
            "written_units": 0,
            "reason": f"Interim access while payment is verified; support request {ticket['id']}",
        },
    )
    assert grant.status_code == 201, grant.text
    assert client.get("/v1/me/access", headers=learner.headers).json()["has_access"] is True
    # 3. Support confirms in the timeline, replies and resolves; the learner is told once.
    assert any(e["kind"] == "access.granted" for e in _kinds(client, agent, learner.id))
    done = client.post(
        f"/v1/staff/support/tickets/{ticket['id']}/messages",
        headers=agent.headers,
        json={"body": "Fixture: access restored while we confirm your payment.", "status": "resolved"},
    )
    assert done.status_code == 200
    events = [n["event"] for n in client.get("/v1/me/notifications", headers=learner.headers).json()["items"]]
    assert events.count("support.resolved") == 1
    assert "support.escalated" in _audited(ticket["id"])
    assert {"support.lookup", "support.timeline_viewed", "entitlement.granted"} <= _audited(str(learner.id))


def test_rehearsal_trial_false_block_appeal(client: TestClient) -> None:
    """Runbook `trial-false-block.md`: a new account on a second-hand phone is refused the trial (device marker). The
    learner appeals; support sees the decision and reason in the timeline; a reviewer issues an account-scoped,
    time-bounded exception; the learner's next claim succeeds. The device marker itself is never cleared."""
    learner = _staff(client, [])
    install = f"fixture-install-{uuid.uuid4().hex}"
    native = {**learner.headers, "X-Portal-Client": "native", "X-Portal-Install": install}

    def claim() -> dict[str, Any]:
        r = client.post(
            "/v1/me/trial/claims",
            headers=native,
            json={
                "surface": "android",
                "idempotency_key": uuid.uuid4().hex,
                "proof": {"fixture_verdict": "consumed"},
                "label": "Fixture second-hand phone",
            },
        )
        assert r.status_code == 200, r.text
        return dict(r.json())

    assert claim()["state"] == "device_used"
    ticket = _request(client, learner, "Fixture: trial refused", "Fixture: I bought this phone second-hand.")
    agent = _staff(client, ["support"], mfa=True)
    decisions = [e for e in _kinds(client, agent, learner.id) if e["kind"] == "trial.claim"]
    assert any(d["detail"]["to_status"] == "CLOSED_INELIGIBLE" for d in decisions)  # the decision and its reason
    exc = client.post(
        "/v1/staff/trial/exceptions",
        headers=agent.headers,
        json={
            "email": learner.email,
            "surface": "android",
            "days": 7,
            "reason": f"Second-hand device; appeal in request {ticket['id']}",
        },
    )
    assert exc.status_code == 201, exc.text
    assert claim()["state"] == "granted"
    kinds = [e["kind"] for e in _kinds(client, agent, learner.id)]
    assert {"trial.exception", "trial.granted", "trial.device_authorized"} <= set(kinds)
    assert "trial.exception_granted" in _audited(str(learner.id))
