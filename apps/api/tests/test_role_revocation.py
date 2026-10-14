"""P18.S1.T2 (part; ROLE-REVOCATION-01): a revoked staff role stops working on the very next request.

Roles are read from the database on every request, not carried in the token. For each staff role, an owner grants it,
the staff member uses an endpoint that needs it, the owner revokes it, and the same session, unchanged, is refused at
once. A role limited to one class and subject never reaches another's work. Labelled fixture accounts only.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from portal_api.db import get_sessionmaker
from tests.test_content_workflow import Staff

CASES: list[tuple[str, dict[str, Any], str]] = [
    ("support", {}, "/v1/staff/support/tickets"),
    ("finance", {}, "/v1/admin/entitlements"),
    ("platform_operator", {}, "/v1/ops/signals"),
    ("subject_reviewer", {"grades": [12], "subjects": ["chemistry"]}, "/v1/studio/written/queue"),
]


@pytest.mark.parametrize(("role", "scope", "path"), CASES)
def test_a_revoked_role_is_refused_on_the_next_request(
    client: TestClient, role: str, scope: dict[str, Any], path: str
) -> None:
    with get_sessionmaker()() as db:
        owner = Staff(client, db, ["owner_admin"], mfa=True)
        person = Staff(client, db, [], mfa=True)
    granted = client.post(
        "/v1/admin/staff",
        headers=owner.headers,
        json={"email": person.email, "role": role, "scope": scope, "reason": "Fixture: role for a sweep"},
    )
    assert granted.status_code == 201, granted.text
    assert client.get(path, headers=person.headers).status_code == 200

    revoked = client.post(
        f"/v1/admin/role-grants/{granted.json()['id']}/revoke",
        headers=owner.headers,
        json={"reason": "Fixture: role removed in a sweep"},
    )
    assert revoked.status_code == 200, revoked.text
    assert client.get(path, headers=person.headers).status_code == 403  # same session, no new sign-in needed


def test_a_scoped_reviewer_never_sees_another_scopes_scripts(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    from tests.test_written_marking import _sealed_script

    _, a = _sealed_script(client, published_written["chapter"])  # Class XII Chemistry
    with get_sessionmaker()() as db:
        inside = Staff(client, db, ["subject_reviewer"], {"grades": [12], "subjects": ["chemistry"]})
        other_subject = Staff(client, db, ["subject_reviewer"], {"grades": [12], "subjects": ["physics"]})
        other_class = Staff(client, db, ["subject_reviewer"], {"grades": [11], "subjects": ["chemistry"]})
    ref = a["id"][:8]
    seen = [c for c in client.get("/v1/studio/written/queue", headers=inside.headers).json() if c["reference"] == ref]
    assert seen
    case = seen[0]["id"]
    for outsider in (other_subject, other_class):
        queue = client.get("/v1/studio/written/queue", headers=outsider.headers).json()
        assert all(c["reference"] != ref for c in queue)
        assert client.get(f"/v1/studio/written/cases/{case}", headers=outsider.headers).status_code in (403, 404)
        assert client.post(f"/v1/studio/written/cases/{case}/lease", headers=outsider.headers).status_code in (403, 404)
