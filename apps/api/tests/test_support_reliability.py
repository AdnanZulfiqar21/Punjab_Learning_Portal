"""P15.S4.T1/T2 and P15.S3.T2: per-account support limits, staff escalation, resolution notices, suppressed
destinations, dead-letter inspection and requeue, and delivery metrics measured apart from reading."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from portal_api.db import get_sessionmaker
from portal_api.modules.notifications import delivery, service
from portal_api.modules.notifications.models import NotificationDelivery
from portal_api.modules.support import service as support
from tests.test_content_workflow import Staff


def _staff(client: TestClient, roles: list[str], mfa: bool = False) -> Staff:
    with get_sessionmaker()() as db:
        return Staff(client, db, roles, mfa=mfa)


def _ticket(client: TestClient, who: Staff, subject: str = "Fixture help") -> dict[str, Any]:
    r = client.post(
        "/v1/support/tickets",
        headers=who.headers,
        json={"category": "technical", "subject": subject, "body": "Fixture: something is wrong."},
    )
    assert r.status_code == 201, r.text
    return dict(r.json())


def _no_quiet(client: TestClient, who: Staff) -> None:
    body = {"timezone": "UTC", "quiet_start": "00:00", "quiet_end": "00:00", "push_enabled": False}
    assert client.put("/v1/me/notification-preferences", headers=who.headers, json=body).status_code == 200


def test_a_learner_is_limited_to_a_number_of_messages_an_hour(client: TestClient) -> None:
    learner = _staff(client, [])
    t = _ticket(client, learner)
    codes = [
        client.post(
            f"/v1/support/tickets/{t['id']}/messages", headers=learner.headers, json={"body": f"Again {i}"}
        ).status_code
        for i in range(support.MAX_LEARNER_MESSAGES_PER_HOUR + 1)
    ]
    assert codes.count(429) >= 1 and codes.index(429) <= support.MAX_LEARNER_MESSAGES_PER_HOUR
    limited = client.post(f"/v1/support/tickets/{t['id']}/messages", headers=learner.headers, json={"body": "More"})
    assert limited.status_code == 429 and limited.json()["title"] == "RATE_LIMITED"


def test_staff_escalate_privately_and_escalated_requests_come_first(client: TestClient) -> None:
    learner, staff = _staff(client, []), _staff(client, ["support"])
    first = _ticket(client, learner, "Fixture older")
    second = _ticket(client, learner, "Fixture newer")
    short = client.post(
        f"/v1/staff/support/tickets/{first['id']}/escalate", headers=staff.headers, json={"reason": "x"}
    )
    assert short.status_code == 422
    ok = client.post(
        f"/v1/staff/support/tickets/{first['id']}/escalate",
        headers=staff.headers,
        json={"reason": "Fixture: needs the academic lead"},
    )
    assert ok.status_code == 200 and ok.json()["escalation_reason"] == "Fixture: needs the academic lead"
    again = client.post(
        f"/v1/staff/support/tickets/{first['id']}/escalate",
        headers=staff.headers,
        json={"reason": "Fixture: again please"},
    )
    assert again.status_code == 409
    queue = [t["id"] for t in client.get("/v1/staff/support/tickets", headers=staff.headers).json()]
    assert queue.index(first["id"]) < queue.index(second["id"])  # escalated first even though older
    mine = client.get(f"/v1/support/tickets/{first['id']}", headers=learner.headers).json()
    assert "escalation_reason" not in mine  # a staff note never reaches the learner


def test_resolving_a_request_tells_the_learner_once(client: TestClient) -> None:
    learner, staff = _staff(client, []), _staff(client, ["support"])
    t = _ticket(client, learner)
    r = client.post(
        f"/v1/staff/support/tickets/{t['id']}/messages",
        headers=staff.headers,
        json={"body": "Fixture: fixed now.", "status": "resolved"},
    )
    assert r.status_code == 200, r.text
    events = [n["event"] for n in client.get("/v1/me/notifications", headers=learner.headers).json()["items"]]
    assert events == ["support.resolved"]


def test_a_suppressed_address_is_never_sent_to(client: TestClient) -> None:
    learner = _staff(client, [])
    _no_quiet(client, learner)
    operator, plain = _staff(client, ["platform_operator"], mfa=True), _staff(client, ["support"], mfa=True)
    body = {"channel": "email", "destination": learner.email, "reason": "Fixture: hard bounce"}
    assert client.post("/v1/ops/notifications/suppressions", headers=plain.headers, json=body).status_code == 403
    assert client.post("/v1/ops/notifications/suppressions", headers=operator.headers, json=body).status_code == 204
    with get_sessionmaker()() as db:
        service.notify(db, learner.id, "support.reply", {"subject": "Fixture"}, dedupe_key="supp-1")
        db.commit()
        delivery.deliver_due(db, limit=100_000)
        d = db.scalar(select(NotificationDelivery).where(NotificationDelivery.user_id == learner.id))
    assert d is not None and d.status == "skipped" and "suppressed" in (d.last_error or "")
    params = {"channel": "email", "destination": learner.email.upper()}  # normalised: case doesn't matter
    assert (
        client.delete("/v1/ops/notifications/suppressions", params=params, headers=operator.headers).status_code == 204
    )
    assert (
        client.delete("/v1/ops/notifications/suppressions", params=params, headers=operator.headers).status_code == 404
    )


def test_dead_letters_can_be_inspected_and_requeued(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    learner = _staff(client, [])
    _no_quiet(client, learner)
    operator = _staff(client, ["platform_operator"], mfa=True)
    with get_sessionmaker()() as db:
        service.notify(db, learner.id, "support.reply", {"subject": "Fixture"}, dedupe_key="dead-1")
        db.commit()

    def broken(*_: Any) -> Any:
        raise RuntimeError("provider down")

    monkeypatch.setitem(delivery.ADAPTERS, "email", broken)
    with get_sessionmaker()() as db:
        for _ in range(delivery.MAX_ATTEMPTS):
            db.execute(
                NotificationDelivery.__table__.update()
                .where(NotificationDelivery.user_id == learner.id)
                .values(next_attempt_at=NotificationDelivery.created_at)
            )
            db.commit()
            delivery.deliver_due(db, limit=100_000)
    monkeypatch.undo()
    letters = client.get("/v1/ops/notifications/dead-letters", headers=operator.headers).json()
    mine = next(
        x for x in letters if x["event"] == "support.reply" and x["last_error"] == "RuntimeError: provider down"
    )
    assert mine["attempts"] == delivery.MAX_ATTEMPTS
    url = f"/v1/ops/notifications/deliveries/{mine['id']}/requeue"
    assert client.post(url, headers=operator.headers).status_code == 204
    assert client.post(url, headers=operator.headers).status_code == 409  # only failed ones
    with get_sessionmaker()() as db:
        delivery.deliver_due(db, limit=100_000)
    metrics = client.get("/v1/ops/notifications/metrics", headers=operator.headers).json()
    assert metrics["deliveries"]["email"].get("sent", 0) >= 1
    assert metrics["inbox"]["support.reply"]["created"] >= 1 and "read" in metrics["inbox"]["support.reply"]
