"""P18.S1.T3 (PRIVILEGED-01): privileged workflows can't be abused from inside. No staff role escalates itself or others
without `manage_roles`; nobody edits a score (scores change only through reviewed corrections); support never reads
answer keys, even with assisted access; an expired or revoked session is refused. Fixture accounts and questions
only."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from portal_api.modules.identity import tokens
from portal_api.modules.identity.models import StaffRoleGrant
from portal_api.modules.identity.permissions import Permission, Role, permissions_for
from tests.test_attempts import POOL, _form, _learner, _start
from tests.test_authorization_matrix import _routes
from tests.test_content_workflow import Staff
from tests.test_mistake_notebook import _answer, _submit

# The only ways a stored score can change. Each needs `adjudicate` + MFA and a reviewed defect (MCQADJ-01, ADJ-01).
SCORE_CHANGING_ROUTES = {
    "POST /v1/studio/items/{item_id}/score-corrections",
    "POST /v1/studio/written/adjudications",
    "POST /v1/studio/written/adjudications/{adjudication_id}/run",
}


def _grants(db: Session, user_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count(StaffRoleGrant.id)).where(
                StaffRoleGrant.user_id == user_id, StaffRoleGrant.revoked_at.is_(None)
            )
        )
        or 0
    )


def test_no_role_without_manage_roles_can_grant_any_role(client: TestClient, db: Session) -> None:
    target = Staff(client, db, [])
    body = {"role": "owner_admin", "scope": {}, "reason": "Fixture: escalation attempt"}
    for role in Role:
        if role == Role.student or Permission.manage_roles in permissions_for({role}):
            continue
        actor = Staff(client, db, [role.value], mfa=True)
        for who in (actor.id, target.id):  # neither for themselves nor for anyone else
            r = client.post(f"/v1/admin/users/{who}/roles", headers=actor.headers, json=body)
            assert r.status_code == 403, (role, r.text)
        db.expire_all()
        assert _grants(db, actor.id) == 1 and _grants(db, target.id) == 0, role
    admin = Staff(client, db, ["owner_admin"], mfa=True)
    me = client.post(f"/v1/admin/users/{admin.id}/roles", headers=admin.headers, json={**body, "role": "finance"})
    assert me.status_code == 403  # even an administrator can't change their own roles


def test_scores_change_only_through_reviewed_corrections() -> None:
    mutating = {
        f"{m} {r.path}"
        for r in _routes()
        for m in r.methods
        if m in ("POST", "PUT", "PATCH", "DELETE") and ("score" in r.path or "adjudication" in r.path)
    }
    assert mutating == SCORE_CHANGING_ROUTES, sorted(mutating ^ SCORE_CHANGING_ROUTES)


def test_support_never_sees_answer_keys_even_with_assisted_access(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    learner = _learner(client)
    form = _form(client, learner, physics["chapter"], count=POOL).json()
    attempt = _start(client, learner, form["id"])
    _answer(client, learner, form["id"], attempt, correct={1})
    _submit(client, learner, attempt["id"])
    ticket = client.post(
        "/v1/support/tickets",
        headers=learner.headers,
        json={"category": "access", "subject": "Fixture: result", "body": "Fixture: please check my result."},
    ).json()
    agent = Staff(client, db, ["support"], mfa=True)
    assert (
        client.post(
            "/v1/staff/support/learners/lookup", headers=agent.headers, json={"email": learner.email}
        ).status_code
        == 200
    )
    url = f"/v1/staff/support/learners/{learner.id}"
    granted = client.post(
        f"{url}/assisted-access",
        headers=agent.headers,
        json={"ticket_id": ticket["id"], "reason": "Fixture: checking the learner's result", "minutes": 10},
    )
    assert granted.status_code == 201, granted.text
    timeline = client.get(f"{url}/timeline", headers=agent.headers)
    assert timeline.status_code == 200
    option_ids = {o["id"] for item in attempt["items"] for o in item["options"]}
    for forbidden in ("correct_option_id", "corrected_key", "explanation", "stem", '"chosen"'):
        assert forbidden not in timeline.text, forbidden
    assert not any(f'"{o}"' in timeline.text for o in option_ids)
    # Support can't open the learner's result or attempt either.
    for path in (f"/v1/attempts/{attempt['id']}/result", f"/v1/attempts/{attempt['id']}"):
        assert client.get(path, headers=agent.headers).status_code == 404


def test_expired_and_revoked_sessions_are_refused(client: TestClient, db: Session) -> None:
    learner = Staff(client, db, [])
    expired = tokens.get_dev_issuer().issue(f"dev|{learner.email}", learner.email, ttl_s=-60)
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    created = client.post("/v1/sessions", headers=learner.headers, json={"kind": "web", "device_label": "Fixture"})
    assert created.status_code == 201, created.text
    session = {"Authorization": f"Bearer {created.json()['session_token']}"}
    assert client.get("/v1/me", headers=session).status_code == 200
    assert client.delete("/v1/me/session", headers=session).status_code == 204
    assert client.get("/v1/me", headers=session).status_code == 401
