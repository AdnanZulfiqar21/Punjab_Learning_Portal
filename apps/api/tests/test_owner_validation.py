"""P16.S4.T3 (OWNER-VALIDATION-01): the owner operations not already shown by OWNER-OPS-01.

Adding staff: only an administrator (with MFA) grants a role, with a scope and a reason; the new reviewer can work
straight away, only inside that scope, and loses access when the grant is revoked. Checking a syllabus update: a
logged notice waits for that reviewer's decision, and the source review clears the stale flag. Publishing,
quarantining and regrading a question, a refund and a trial appeal are in `tests/test_owner_operations.py`. Accounts
and notices are labelled technical fixtures.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.modules.audit.models import AuditEvent
from tests.test_content_workflow import Staff, _chapter

SCOPE = {"grades": [11], "subjects": ["physics"]}


def test_adding_staff_and_checking_a_syllabus_update(client: TestClient, db: Session) -> None:
    admin, finance = Staff(client, db, ["owner_admin"], mfa=True), Staff(client, db, ["finance"], mfa=True)
    author, newcomer = Staff(client, db, ["content_author"], SCOPE), Staff(client, db, [])
    grant = {
        "email": newcomer.email.upper(),
        "role": "subject_reviewer",
        "scope": SCOPE,
        "reason": "Fixture: new reviewer",
    }
    url = "/v1/admin/staff"  # the owner's staff screen: by exact email, no database or command line needed
    assert client.post(url, headers=finance.headers, json=grant).status_code == 403
    assert client.post(url, headers=Staff(client, db, ["owner_admin"]).headers, json=grant).status_code == 403  # MFA
    unknown = client.post(url, headers=admin.headers, json={**grant, "email": "nobody-here@example.invalid"})
    assert unknown.status_code == 404 and "create an account first" in unknown.json()["detail"]
    made = client.post(url, headers=admin.headers, json=grant)
    assert made.status_code == 201, made.text
    listed = client.get(url, headers=admin.headers).json()
    assert any(g["email"] == newcomer.email and g["role"] == "subject_reviewer" for g in listed)
    assert client.get(url, headers=finance.headers).status_code == 403
    db.expire_all()
    assert db.scalar(
        select(AuditEvent.id).where(AuditEvent.action == "role.grant", AuditEvent.target_id == str(newcomer.id))
    )

    # The new reviewer decides a logged syllabus notice and records the source review, inside their scope only.
    notice_body = {
        "grade": 11,
        "subject": "physics",
        "title": "Fixture syllabus notice (owner validation)",
        "source_url": "https://example.invalid/notice",
        "summary": "Fixture: a chapter order change was announced.",
    }
    logged = client.post("/v1/studio/syllabus-notices", headers=author.headers, json=notice_body)
    assert logged.status_code == 201, logged.text
    notice = next(n for n in logged.json() if n["title"] == notice_body["title"] and n["status"] == "open")
    decision = {"accept": True, "decision": "Fixture: plan revisions for the reordered chapter"}
    decided = client.post(
        f"/v1/studio/syllabus-notices/{notice['id']}/decision", headers=newcomer.headers, json=decision
    )
    assert decided.status_code == 200, decided.text
    _, doc = _chapter(db, 11, "physics")
    _, other = _chapter(db, 12, "physics")
    review = {"note": "Fixture: checked the edition against the notice"}
    assert client.post(f"/v1/studio/sources/{doc.id}/review", headers=newcomer.headers, json=review).status_code == 204
    assert (
        client.post(f"/v1/studio/sources/{other.id}/review", headers=newcomer.headers, json=review).status_code == 403
    )
    sources = client.get("/v1/studio/sources", headers=newcomer.headers).json()
    assert next(s for s in sources if s["id"] == str(doc.id))["review_stale"] is False

    # Revoked: the access ends at once.
    revoked = client.post(
        f"/v1/admin/role-grants/{made.json()['id']}/revoke", headers=admin.headers, json={"reason": "Fixture: left"}
    )
    assert revoked.status_code == 200, revoked.text
    assert client.post(f"/v1/studio/sources/{doc.id}/review", headers=newcomer.headers, json=review).status_code == 403
    assert not any(g["email"] == newcomer.email for g in client.get(url, headers=admin.headers).json())
