"""W08.S1.T3 (PERMITS-01): expiry and revocation of written permits (roadmap §20.13.4).

* **Ordinary expiry:** a test started before the plan ended may be finished under its pinned terms, and its marking
  continues; a new test needs a current plan.
* **Withdrawal (refund or fraud revocation):** the unsealed tests the plan funded end at once, their reservation is
  returned, and uploaded pages are kept. Sealed (accepted) work is untouched: it is still marked and its result is
  shown. Nothing retained is erased.

Grants, scripts and marks are labelled technical fixtures.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from portal_api.db import get_sessionmaker
from portal_api.modules.access.models import AllowanceEvent, Entitlement
from portal_api.modules.audit.models import AuditEvent
from tests.test_content_workflow import Staff
from tests.test_entitlement_scope import _finance, _grant
from tests.test_written_attempts import _form, _learner, _map, _png, _seal, _start, _upload
from tests.test_written_marking import GOOD, _case_for, _decide, _reviewer


def _submit(client: TestClient, who: Staff, attempt: dict[str, Any], seed: int) -> None:
    page = _upload(client, who, attempt["id"], _png(seed=seed)).json()["pages"][0]["id"]
    m = _map(client, who, attempt, {"1:a": {"pages": [page]}, "1:b": {"unanswered": True}}).json()
    assert _seal(client, who, attempt["id"], m["manifest_revision"]).status_code == 200


def _mark_and_release(client: TestClient, attempt_id: str) -> None:
    reviewer = _reviewer(client)
    case = _case_for(client, reviewer, attempt_id)
    client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=reviewer.headers)
    assert _decide(client, reviewer, case["id"], 0, GOOD, release=True).status_code == 200


def test_a_test_started_before_the_plan_ended_can_still_be_finished(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner = _learner(client)  # on the free trial
    started = _start(client, learner, published_written["chapter"])
    with get_sessionmaker()() as db:  # the plan ends after the test started
        db.execute(  # the plan ends now, after the test started
            update(Entitlement)
            .where(Entitlement.user_id == learner.id)
            .values(starts_at=Entitlement.starts_at - timedelta(days=1), ends_at=func.now())
        )
        db.commit()
    # A new test needs a current plan...
    refused = _form(client, learner, published_written["chapter"])
    assert refused.status_code == 403 and refused.json()["title"] == "ACCESS_REQUIRED"
    # ...but the already-started one is honoured: upload, submit, marking and the result all continue.
    _submit(client, learner, started, seed=61)
    _mark_and_release(client, started["id"])
    result = client.get(f"/v1/written-attempts/{started['id']}/result", headers=learner.headers).json()
    assert result["status"] == "released" and result["total_units"] == 100


def test_a_withdrawn_plan_ends_unsealed_tests_and_keeps_accepted_work(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    chapter = published_written["chapter"]
    with get_sessionmaker()() as db:
        finance = _finance(client, db)
        learner = Staff(client, db, [])
    grant = _grant(client, finance, learner, None, units=20)
    assert grant.status_code == 201, grant.text
    sealed = _start(client, learner, chapter)
    _submit(client, learner, sealed, seed=62)
    open_attempt = _start(client, learner, chapter)
    _upload(client, learner, open_attempt["id"], _png(seed=63))

    revoked = client.post(
        f"/v1/admin/entitlements/{grant.json()['id']}/revoke",
        headers=finance.headers,
        json={"reason": "Fixture: refund issued"},
    )
    assert revoked.status_code == 200, revoked.text

    # The unsealed test has ended, saying why; its pages are kept and its reservation returned.
    ended = client.get(f"/v1/written-attempts/{open_attempt['id']}", headers=learner.headers).json()
    assert ended["status"] == "expired" and ended["end_reason"] == "plan_withdrawn" and len(ended["pages"]) == 1
    more = _upload(client, learner, open_attempt["id"], _png(seed=64))
    assert more.status_code == 409 and more.json()["code_reason"] == "PERMIT_WITHDRAWN"
    with get_sessionmaker()() as db:
        kinds = db.scalars(select(AllowanceEvent.kind).where(AllowanceEvent.attempt_id == open_attempt["id"])).all()
        assert sorted(kinds) == ["RELEASED", "RESERVED"]
        audited = db.scalars(select(AuditEvent.action).where(AuditEvent.target_id == open_attempt["id"])).all()
        assert "written.permit_withdrawn" in audited

    # Accepted work continues: the sealed script is still marked and its result shown.
    assert client.get(f"/v1/written-attempts/{sealed['id']}", headers=learner.headers).json()["status"] == "sealed"
    _mark_and_release(client, sealed["id"])
    result = client.get(f"/v1/written-attempts/{sealed['id']}/result", headers=learner.headers).json()
    assert result["status"] == "released" and result["total_units"] == 100
    # And nothing new starts on the withdrawn plan.
    assert _form(client, learner, chapter).status_code == 403
