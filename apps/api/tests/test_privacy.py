"""P18.S3.T2 (PRIVACY-01): a person can export their own data (no secrets, no staff notes, nobody else's data) and
request deletion, which is recorded and routed to support without any automatic erasure. Fixture accounts only."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from portal_api.db import get_sessionmaker
from portal_api.modules.audit.models import AuditEvent
from tests.test_content_workflow import Staff


def _staff(client: TestClient, roles: list[str]) -> Staff:
    with get_sessionmaker()() as db:
        return Staff(client, db, roles)


def test_export_contains_my_data_only_without_secrets_or_staff_notes(client: TestClient) -> None:
    me, other, agent = _staff(client, []), _staff(client, []), _staff(client, ["support"])
    assert client.post("/v1/me/trial", headers=me.headers).status_code == 200
    mine = client.post(
        "/v1/support/tickets",
        headers=me.headers,
        json={"category": "account", "subject": "Fixture: my question", "body": "Fixture: my own words."},
    ).json()
    client.post(
        "/v1/support/tickets",
        headers=other.headers,
        json={"category": "account", "subject": "Fixture: someone else", "body": "Fixture: not yours."},
    )
    client.post(
        f"/v1/staff/support/tickets/{mine['id']}/messages",
        headers=agent.headers,
        json={"body": "Fixture internal note: staff only.", "internal": True},
    )
    client.post(
        f"/v1/staff/support/tickets/{mine['id']}/escalate",
        headers=agent.headers,
        json={"reason": "Fixture escalation note, staff only"},
    )
    r = client.get("/v1/me/data-export", headers=me.headers)
    assert r.status_code == 200 and r.headers["content-disposition"].startswith("attachment;")
    assert r.headers["cache-control"] == "private, no-store"
    data = json.loads(r.content)
    assert data["format"] == "portal-personal-data-export" and data["account"]["email"] == me.email
    assert data["trial"]["grants"] and data["access"]
    assert "Fixture: my own words." in r.text
    for absent in ("staff only", "Fixture: not yours.", other.email, agent.email, "token_hash", "installation_ref"):
        assert absent not in r.text, absent
    assert all("author_id" not in m for m in data["help_requests"]["messages"])
    with get_sessionmaker()() as db:
        assert db.scalar(
            select(AuditEvent.id).where(AuditEvent.action == "privacy.data_exported", AuditEvent.actor_user_id == me.id)
        )
    assert client.get("/v1/me/data-export").status_code == 401


def test_a_deletion_request_is_recorded_and_routed_to_support_without_erasing_anything(client: TestClient) -> None:
    me, agent = _staff(client, []), _staff(client, ["support"])
    url = "/v1/me/deletion-request"
    assert client.post(url, headers=me.headers, json={"confirm_email": "wrong@example.com"}).status_code == 422
    r = client.post(url, headers=me.headers, json={"confirm_email": me.email.upper(), "reason": "Fixture: leaving"})
    assert r.status_code == 202, r.text
    ticket = r.json()["ticket_id"]
    assert client.post(url, headers=me.headers, json={"confirm_email": me.email}).status_code == 409
    queue = client.get("/v1/staff/support/tickets", headers=agent.headers).json()
    assert any(t["id"] == ticket and t["subject"] == "Account deletion request" for t in queue)
    assert client.get("/v1/me", headers=me.headers).status_code == 200  # nothing erased automatically (B15)


def test_every_per_person_table_is_exported_or_excluded_with_a_reason() -> None:
    """OCT9 coverage inventory: a new table holding one person's rows can't be silently left out of the export."""
    import importlib
    import pkgutil

    import portal_api
    from portal_api.db import Base
    from portal_api.modules.identity.privacy import EXPORTED_TABLES, NOT_EXPORTED

    for m in pkgutil.walk_packages(portal_api.__path__, "portal_api."):
        if not m.name.endswith(("__main__", "export_openapi")):
            importlib.import_module(m.name)
    personal = {
        t.name
        for t in Base.metadata.tables.values()
        if {c.name for c in t.columns} & {"user_id", "owner_id", "requested_by"}
    }
    assert personal - EXPORTED_TABLES - set(NOT_EXPORTED) == set()
    assert EXPORTED_TABLES & set(NOT_EXPORTED) == set()
