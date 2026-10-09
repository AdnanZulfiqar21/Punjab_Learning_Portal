"""OCT9-06: authorisation with *valid* requests. Each protected action is tried with a real object and a valid body by a
plain learner, an out-of-scope staff member and a staff member without MFA; each is refused with 403 and nothing
changes. The accepted staff member then succeeds, which proves the payload was valid all along. Fixture data only."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from tests import test_content_workflow
from tests.test_attempts import POOL, _form, _learner, _start
from tests.test_content_workflow import Staff, _confirm_rights, _post, _submitted
from tests.test_mocks import _publish_profile

team = test_content_workflow.team


def _state(client: TestClient, who: Staff, item_id: str) -> str:
    return str(client.get(f"/v1/studio/items/{item_id}", headers=who.headers).json()["state"])


def test_publishing_needs_the_role_the_scope_and_mfa(client: TestClient, db: Session, team: dict[str, Staff]) -> None:
    item, _, doc = _submitted(client, db, team)
    _confirm_rights(client, db, doc)
    review = {"decision": "approve", "comment": "Fixture check"}
    assert _post(client, team["reviewer"], item["id"], "review", review).status_code == 200
    before = _state(client, team["author"], item["id"])
    other_scope = Staff(client, db, ["publisher"], {"grades": [12], "subjects": ["physics"]}, mfa=True)
    for who in (team["student"], team["outsider"], other_scope, team["publisher_no_mfa"]):
        r = _post(client, who, item["id"], "publish")
        assert r.status_code == 403, r.text
        assert _state(client, team["author"], item["id"]) == before  # nothing changed
    assert _post(client, team["publisher"], item["id"], "publish").status_code == 200


def test_help_authoring_needs_the_permission_and_mfa_to_publish(client: TestClient, db: Session) -> None:
    body = {
        "slug": f"fixture-{uuid.uuid4().hex[:8]}",
        "title": "Fixture article",
        "summary": "Fixture summary",
        "markdown": "Fixture body text for an authorisation test.",
    }
    learner = Staff(client, db, [], mfa=True)
    support, support_mfa = Staff(client, db, ["support"]), Staff(client, db, ["support"], mfa=True)
    assert client.put("/v1/studio/help/articles", headers=learner.headers, json=body).status_code == 403
    listed = client.get("/v1/studio/help/articles", headers=support.headers).json()
    assert all(a["slug"] != body["slug"] for a in listed)  # the refused save created nothing
    saved = client.put("/v1/studio/help/articles", headers=support.headers, json=body)
    assert saved.status_code == 200, saved.text  # drafting needs no MFA
    publish = f"/v1/studio/help/articles/{saved.json()['id']}/publish"
    assert client.post(publish, headers=learner.headers).status_code == 403
    assert client.post(publish, headers=support.headers).status_code == 403  # no MFA
    assert client.get(f"/v1/help/articles/{body['slug']}").status_code == 404  # still unpublished
    assert client.post(publish, headers=support_mfa.headers).status_code == 200


def test_scheduling_a_mock_needs_the_permission_and_mfa(client: TestClient, db: Session) -> None:
    code = _publish_profile(client, db, [{"subject": "physics", "grades": [11], "questions": 2}])
    now = datetime.now(UTC)
    body = {
        "profile_code": code,
        "title": f"Fixture authz {uuid.uuid4().hex[:8]}",
        "starts_at": (now + timedelta(hours=1)).isoformat(),
        "entry_closes_at": (now + timedelta(hours=1, minutes=10)).isoformat(),
        "window_closes_at": (now + timedelta(hours=2)).isoformat(),
        "results_at": (now + timedelta(hours=3)).isoformat(),
    }

    def count() -> int:
        with get_sessionmaker()() as s:
            return int(
                s.execute(text("select count(*) from mock_session where title = :t"), {"t": body["title"]}).scalar_one()
            )

    for who in (Staff(client, db, [], mfa=True), Staff(client, db, ["academic_adjudicator"])):
        assert client.post("/v1/admin/mock-sessions", headers=who.headers, json=body).status_code == 403
        assert count() == 0
    ok = Staff(client, db, ["academic_adjudicator"], mfa=True)
    assert client.post("/v1/admin/mock-sessions", headers=ok.headers, json=body).status_code == 201
    assert count() == 1


def test_another_learners_attempt_is_invisible(client: TestClient, physics: dict[str, Any]) -> None:
    a, b = _learner(client), _learner(client)
    form = _form(client, a, physics["chapter"], count=POOL).json()
    attempt = _start(client, a, form["id"])
    for url in (f"/v1/attempts/{attempt['id']}", f"/v1/attempts/{attempt['id']}/result"):
        assert client.get(url, headers=b.headers).status_code == 404
    assert client.post(f"/v1/practice/forms/{form['id']}/attempt", headers=b.headers).status_code == 404
