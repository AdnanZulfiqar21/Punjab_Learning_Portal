"""P04.S4.T3 (BOUNDARIES-01): account boundaries hold for another learner and for every staff role.

A second learner and a user of every staff role (with MFA, scoped roles on the same class and subject) try every
learner-owned object route with someone else's attempt, test, ticket, notebook entry, notification and trial device:
nothing succeeds, every read is 403 or 404, and no response carries the owner's email or private text. Staff reach
learner data only through their own audited, redacted routes. A suspended account's token stops working at once.
The business, funnel, learning, economics and trial reports and the application's logs carry no learner email or
private text. Accounts and content are labelled technical fixtures.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from portal_api.modules.identity.permissions import STAFF_ROLES
from tests.test_attempts import _form, _learner, _op, _save_ops, _start
from tests.test_authorization_matrix import _routes
from tests.test_content_workflow import Staff
from tests.test_mcq_corrections import _keys
from tests.test_trial_claims import _claim, _install

SCOPE = {"grades": [11], "subjects": ["physics"]}
PARAMS = ("attempt_id", "form_id", "ticket_id", "entry_id", "notification_id", "device_id")
REPORTS = (
    "/v1/admin/business-overview",
    "/v1/admin/analytics/funnel",
    "/v1/admin/analytics/learning?grade=11&subject=physics",
    "/v1/admin/analytics/economics",
    "/v1/admin/analytics/trial-decisions",
)


def test_nobody_else_reaches_a_learners_private_objects(
    client: TestClient, db: Session, physics: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    run = uuid.uuid4().hex[:8]
    victim = _learner(client)
    secret = f"Fixture private words {run}"

    form = _form(client, victim, physics["chapter"], count=2).json()
    attempt = _start(client, victim, form["id"])
    keys = _keys(form["id"])
    wrong = next(o for o in ("o1", "o2", "o3", "o4") if o != keys[1])
    assert _save_ops(client, victim, attempt["id"], _op(1, 1, wrong), _op(2, 1, keys[2])).status_code == 200
    client.post(
        f"/v1/attempts/{attempt['id']}/submit",
        headers=victim.headers,
        json={"idempotency_key": uuid.uuid4().hex, "ops": []},
    )
    entry = client.get("/v1/me/notebook", headers=victim.headers).json()[0]["id"]
    ticket = client.post(
        "/v1/support/tickets",
        headers=victim.headers,
        json={"category": "account", "subject": f"Fixture question {run}", "body": secret},
    ).json()["id"]
    device = _claim(client, victim, _install()).json()["device_id"]
    notes = client.get("/v1/me/notifications", headers=victim.headers).json()["items"]
    notification = notes[0]["id"] if notes else str(uuid.uuid4())
    ids = {
        "attempt_id": attempt["id"],
        "form_id": form["id"],
        "ticket_id": ticket,
        "entry_id": entry,
        "notification_id": notification,
        "device_id": device,
    }

    intruders = {"another learner": _learner(client)}
    for role in sorted(STAFF_ROLES, key=lambda r: r.value):
        intruders[role.value] = Staff(client, db, [role.value], SCOPE, mfa=True)
    routes = [
        r
        for r in _routes()
        if any(f"{{{p}}}" in r.path for p in PARAMS)
        and r.path.startswith(("/v1/attempts/", "/v1/practice/forms/", "/v1/support/tickets/", "/v1/me/"))
    ]
    assert len(routes) >= 10
    breaches = []
    for who, intruder in intruders.items():
        for route in routes:
            url = route.path
            for name, value in ids.items():
                url = url.replace(f"{{{name}}}", value)
            url = url.replace("{position}", "1").replace("{version_id}", str(uuid.uuid4()))
            url = url.replace("{attachment_id}", str(uuid.uuid4()))
            for method in route.methods:
                r = client.request(method, url, headers=intruder.headers, json=None if method == "GET" else {})
                if r.status_code < 400 or (method == "GET" and r.status_code not in (403, 404)):
                    breaches.append(f"{who}: {method} {route.path} -> {r.status_code}")
                if victim.email in r.text or secret in r.text:
                    breaches.append(f"{who}: {method} {route.path} echoed private data")
    assert breaches == []
    # The owner's objects are untouched.
    assert client.get(f"/v1/support/tickets/{ticket}", headers=victim.headers).json()["messages"][0]["body"] == secret

    # Reports and logs carry no learner email or private text.
    owner = Staff(client, db, ["owner_admin"], mfa=True)
    for path in REPORTS:
        r = client.get(path, headers=owner.headers)
        assert r.status_code == 200, (path, r.status_code)
        assert victim.email not in r.text and secret not in r.text and str(victim.id) not in r.text, path
    app_logs = " ".join(json.dumps(x.__dict__, default=str) for x in caplog.records if x.name.startswith("portal"))
    assert app_logs and victim.email not in app_logs and secret not in app_logs

    # A suspended account's token stops working at once, for its own data too.
    reason = {"reason": "Fixture: boundary check"}
    assert client.post(f"/v1/admin/users/{victim.id}/suspend", headers=owner.headers, json=reason).status_code == 200
    for path in ("/v1/me", "/v1/me/data-export", f"/v1/attempts/{attempt['id']}/result"):
        assert client.get(path, headers=victim.headers).status_code in (401, 403), path
