"""P16.S4.T1 (AUDIT-01): owner/admins search the redacted audit trail with MFA; the trail is append-only."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from portal_api.db import get_sessionmaker
from portal_api.modules.audit.models import record
from portal_api.modules.audit.router import redact
from tests.test_content_workflow import Staff


def _staff(client: TestClient, roles: list[str], mfa: bool = True) -> Staff:
    with get_sessionmaker()() as db:
        return Staff(client, db, roles, mfa=mfa)


def test_search_filters_paginates_and_is_restricted(client: TestClient) -> None:
    owner, operator = _staff(client, ["owner_admin"]), _staff(client, ["platform_operator"])
    for reason in ("Fixture switch one", "Fixture switch two", "Fixture switch three"):
        client.put(
            "/v1/ops/features/content_exports", headers=operator.headers, json={"enabled": True, "reason": reason}
        )
    assert client.get("/v1/admin/audit", headers=_staff(client, ["owner_admin"], mfa=False).headers).status_code == 403
    assert client.get("/v1/admin/audit", headers=operator.headers).status_code == 403
    page = client.get(
        "/v1/admin/audit",
        headers=owner.headers,
        params={"action": "ops.", "actor_email": operator.email, "limit": 2},
    )
    assert page.status_code == 200, page.text
    body = page.json()
    assert len(body["events"]) == 2 and body["next_before"]
    assert all(e["action"] == "ops.feature_switched" and e["actor"] == operator.email for e in body["events"])
    assert body["events"][0]["details"]["reason"] == "Fixture switch three"  # newest first
    rest = client.get(
        "/v1/admin/audit",
        headers=owner.headers,
        params={"action": "ops.feature_switched", "actor_email": operator.email, "before": body["next_before"]},
    ).json()
    assert [e["details"]["reason"] for e in rest["events"]] == ["Fixture switch one"] and rest["next_before"] is None
    assert client.get("/v1/admin/audit", headers=owner.headers, params={"before": "junk"}).status_code == 422


def test_sensitive_payload_values_are_redacted() -> None:
    assert redact({"reason": "ok", "email": "a@b", "nested": [{"token_hash": "x", "n": 1}]}) == {
        "reason": "ok",
        "email": "[redacted]",
        "nested": [{"token_hash": "[redacted]", "n": 1}],
    }


def test_the_audit_trail_cannot_be_edited_or_deleted(client: TestClient) -> None:  # client: migrated database
    with get_sessionmaker()() as db:
        record(db, actor=None, action="fixture.append_only_check", target_type="fixture", target_id="1")
        db.commit()
        for stmt in ("update audit_event set action = 'tampered'", "delete from audit_event"):
            with pytest.raises(DBAPIError, match="append-only"):
                db.execute(text(stmt))
            db.rollback()
