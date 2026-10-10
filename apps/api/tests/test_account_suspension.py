"""P18.S4.T2 (SUSPEND-01): incident response can stop one compromised account at once (all its sessions revoked, its
tokens refused) without touching anyone else's work, and reinstate it later. Administrator, MFA, audited, never
yourself. Fixture accounts and questions only."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.modules.audit.models import AuditEvent
from tests.test_attempts import POOL, _form, _learner, _op, _save_ops, _start
from tests.test_content_workflow import Staff


def test_suspension_is_immediate_scoped_and_reversible(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    victim, bystander = _learner(client), _learner(client)
    session = client.post("/v1/sessions", headers=victim.headers, json={"kind": "web"}).json()["session_token"]
    form = _form(client, bystander, physics["chapter"], count=POOL).json()
    attempt = _start(client, bystander, form["id"])  # someone else is mid-test during the incident
    admin, no_mfa = Staff(client, db, ["owner_admin"], mfa=True), Staff(client, db, ["owner_admin"])
    url = f"/v1/admin/users/{victim.id}/suspend"
    body = {"reason": "Fixture: credentials reported stolen"}
    assert client.post(url, headers=no_mfa.headers, json=body).status_code == 403
    assert client.post(url, headers=victim.headers, json=body).status_code == 403
    assert client.post(f"/v1/admin/users/{admin.id}/suspend", headers=admin.headers, json=body).status_code == 403
    r = client.post(url, headers=admin.headers, json=body)
    assert r.status_code == 200 and r.json()["status"] == "suspended", r.text
    assert client.get("/v1/me", headers=victim.headers).status_code == 403  # tokens refused at once
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {session}"}).status_code == 401  # sessions revoked
    first = attempt["items"][0]
    saved = _save_ops(client, bystander, attempt["id"], _op(first["position"], 1, first["options"][0]["id"]))
    assert saved.status_code == 200  # nobody else is affected
    back = client.post(
        f"/v1/admin/users/{victim.id}/reinstate", headers=admin.headers, json={"reason": "Fixture: resolved"}
    )
    assert back.status_code == 200 and back.json()["status"] == "active"
    assert client.get("/v1/me", headers=victim.headers).status_code == 200
    assert client.post(f"/v1/admin/users/{uuid.uuid4()}/suspend", headers=admin.headers, json=body).status_code == 404
    actions = set(db.scalars(select(AuditEvent.action).where(AuditEvent.target_id == str(victim.id))))
    assert {"account.suspended", "account.reinstated"} <= actions
