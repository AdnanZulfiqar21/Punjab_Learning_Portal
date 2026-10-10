"""Incident response for scheduled mocks (P18.S4.T2 with SCHEDULE-01): staff can only *postpone* a session's results,
with a reason, MFA and an audit record; the held result follows the live release time. Fixture profiles only."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.modules.audit.models import AuditEvent
from tests.test_content_workflow import Staff
from tests.test_mock_sessions import _schedule
from tests.test_mocks import _publish_profile


def test_results_can_be_postponed_never_brought_forward(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    code = _publish_profile(
        client, db, [{"subject": "physics", "grades": [11], "questions": 2}], solution_release="after_window"
    )
    admin = Staff(client, db, ["academic_adjudicator"], mfa=True)
    session = _schedule(client, admin, code)
    url = f"/v1/admin/mock-sessions/{session['id']}/postpone-results"
    current = datetime.fromisoformat(session["results_at"])
    later = {"results_at": (current + timedelta(hours=2)).isoformat(), "reason": "Fixture: outage during the window"}
    assert client.post(url, headers=Staff(client, db, ["academic_adjudicator"]).headers, json=later).status_code == 403
    assert client.post(url, headers=Staff(client, db, [], mfa=True).headers, json=later).status_code == 403
    earlier = {"results_at": (current - timedelta(minutes=30)).isoformat(), "reason": "Fixture: bring forward"}
    r = client.post(url, headers=admin.headers, json=earlier)
    assert r.status_code == 422, r.text
    ok = client.post(url, headers=admin.headers, json=later)
    assert ok.status_code == 200, ok.text
    assert datetime.fromisoformat(ok.json()["results_at"]) == current + timedelta(hours=2)
    logged = db.scalars(
        select(AuditEvent).where(
            AuditEvent.action == "mock_session.results_postponed", AuditEvent.target_id == session["id"]
        )
    ).all()
    assert len(logged) == 1 and logged[0].details["reason"] == later["reason"]
