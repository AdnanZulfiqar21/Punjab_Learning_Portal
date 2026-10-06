"""Identity, authorisation and onboarding (P04). Uses the dev-only issuer and isolated technical identities."""

from __future__ import annotations

import time
import uuid
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.config import Settings, get_settings
from portal_api.modules.audit.models import AuditEvent
from portal_api.modules.identity import cli, tokens
from portal_api.modules.identity.models import AppUser, StaffRoleGrant


def _email() -> str:
    return f"tester-{uuid.uuid4().hex[:10]}@example.com"


def _login(client: TestClient, email: str, password: str = "correct-horse-battery", mfa: bool = False) -> str:
    r = client.post("/v1/dev-auth/register", json={"email": email, "password": password})
    assert r.status_code == 202
    t = client.post("/v1/dev-auth/token", json={"email": email, "password": password, "mfa": mfa})
    assert t.status_code == 200, t.text
    return str(t.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------ authentication
def test_registration_and_login_are_enumeration_safe(client: TestClient) -> None:
    email = _email()
    first = client.post("/v1/dev-auth/register", json={"email": email, "password": "correct-horse-battery"})
    again = client.post("/v1/dev-auth/register", json={"email": email, "password": "different-password-x"})
    assert first.status_code == again.status_code == 202 and first.json() == again.json()
    wrong = client.post("/v1/dev-auth/token", json={"email": email, "password": "wrong-password"})
    unknown = client.post("/v1/dev-auth/token", json={"email": _email(), "password": "wrong-password"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]
    # The second registration did not change the password.
    assert (
        client.post("/v1/dev-auth/token", json={"email": email, "password": "correct-horse-battery"}).status_code == 200
    )


def test_short_passwords_are_rejected(client: TestClient) -> None:
    r = client.post("/v1/dev-auth/register", json={"email": _email(), "password": "short"})
    assert r.status_code == 422


def test_me_requires_a_valid_token(client: TestClient) -> None:
    r = client.get("/v1/me")
    assert r.status_code == 401 and r.headers["www-authenticate"].startswith("Bearer")
    assert client.get("/v1/me", headers=_auth("not-a-jwt")).status_code == 401
    expired = tokens.get_dev_issuer().issue("dev|ghost@example.com", None, ttl_s=-3600)
    assert client.get("/v1/me", headers=_auth(expired)).status_code == 401


def test_tokens_from_untrusted_issuers_or_wrong_audience_are_rejected(client: TestClient) -> None:
    foreign_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(time.time())
    base = {"sub": "attacker", "iat": now, "exp": now + 300}
    forged_dev = jwt.encode({**base, "iss": get_settings().dev_auth_issuer, "aud": "portal-api"}, foreign_key, "RS256")
    other_iss = jwt.encode({**base, "iss": "https://evil.example", "aud": "portal-api"}, foreign_key, "RS256")
    for tok in (forged_dev, other_iss):
        assert client.get("/v1/me", headers=_auth(tok)).status_code == 401
    issuer = tokens.get_dev_issuer()
    wrong_aud = jwt.encode(
        {**base, "iss": issuer.issuer, "aud": "another-app"}, issuer._key, "RS256", headers={"kid": issuer.kid}
    )
    assert client.get("/v1/me", headers=_auth(wrong_aud)).status_code == 401


def test_oidc_provider_tokens_are_verified_through_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Managed-provider path (Cognito-style access token: audience in client_id, token_use=access)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    settings = Settings(oidc_issuer="https://idp.example.org/pool", oidc_audience="app-client-1")

    class FakeJwks:
        def get_signing_key_from_jwt(self, _token: str) -> Any:
            return type("K", (), {"key": key.public_key()})()

    monkeypatch.setattr(tokens, "_jwks_client", lambda _url: FakeJwks())
    now = int(time.time())
    claims = {
        "iss": "https://idp.example.org/pool",
        "sub": "abc",
        "iat": now,
        "exp": now + 300,
        "client_id": "app-client-1",
        "token_use": "access",
        "amr": ["pwd", "mfa"],
    }
    ok = tokens.verify(jwt.encode(claims, key, "RS256"), settings)
    assert ok.subject == "abc" and ok.mfa is True
    with pytest.raises(tokens.InvalidToken):
        tokens.verify(jwt.encode({**claims, "token_use": "id"}, key, "RS256"), settings)
    with pytest.raises(tokens.InvalidToken):
        tokens.verify(jwt.encode({**claims, "client_id": "other"}, key, "RS256"), settings)


# ------------------------------------------------------------------ account and onboarding
def test_first_sign_in_creates_one_account_and_profile_roundtrips(client: TestClient, db: Session) -> None:
    email = _email()
    token = _login(client, email)
    me = client.get("/v1/me", headers=_auth(token))
    assert me.status_code == 200 and me.headers["cache-control"] == "private, no-store"
    body = me.json()
    assert body["email"] == email and body["roles"] == [] and body["profile"] is None
    client.get("/v1/me", headers=_auth(token))
    assert len(db.scalars(select(AppUser).where(AppUser.email == email)).all()) == 1

    profile = {
        "grade": 12,
        "stream": "pre_medical",
        "subjects": ["biology", "chemistry", "physics"],
        "target_exams": ["mdcat"],
        "target_year": 2027,
        "explanation_language": "en",
        "daily_minutes": 90,
    }
    r = client.put("/v1/me/profile", json=profile, headers=_auth(token))
    assert r.status_code == 200 and r.json()["grade"] == 12
    assert client.get("/v1/me", headers=_auth(token)).json()["profile"]["subjects"] == profile["subjects"]


@pytest.mark.parametrize(
    "bad",
    [
        {"grade": 10},
        {"subjects": ["english"]},
        {"subjects": ["biology", "biology"]},
        {"daily_minutes": 5},
        {"cnic": "12345-1234567-1"},  # identity documents are never collected
    ],
)
def test_profile_validation(client: TestClient, bad: dict[str, Any]) -> None:
    token = _login(client, _email())
    assert client.put("/v1/me/profile", json=bad, headers=_auth(token)).status_code == 422


def test_consent_is_versioned_idempotent_and_terms_cannot_be_casually_withdrawn(client: TestClient) -> None:
    token = _login(client, _email())
    a = client.post("/v1/me/consents", json={"document": "terms", "version": "2026-10"}, headers=_auth(token))
    b = client.post("/v1/me/consents", json={"document": "terms", "version": "2026-10"}, headers=_auth(token))
    assert a.status_code == b.status_code == 201 and a.json()["accepted_at"] == b.json()["accepted_at"]
    assert client.delete("/v1/me/consents/terms", headers=_auth(token)).status_code == 409
    client.post("/v1/me/consents", json={"document": "marketing_messages", "version": "1"}, headers=_auth(token))
    assert client.delete("/v1/me/consents/marketing_messages", headers=_auth(token)).status_code == 204
    consents = client.get("/v1/me", headers=_auth(token)).json()["consents"]
    marketing = [c for c in consents if c["document"] == "marketing_messages"]
    assert marketing and marketing[0]["withdrawn_at"] is not None


# ------------------------------------------------------------------ roles and authorisation
def _make_owner(client: TestClient) -> tuple[str, str]:
    email = _email()
    _login(client, email)
    client.get("/v1/me", headers=_auth(_login(client, email)))
    assert cli.main(["--email", email, "--role", "owner_admin", "--reason", "test bootstrap owner"]) == 0
    return email, _login(client, email, mfa=True)


def test_students_cannot_reach_admin_operations(client: TestClient) -> None:
    student = _login(client, _email())
    me = client.get("/v1/me", headers=_auth(student)).json()
    r = client.post(
        f"/v1/admin/users/{me['id']}/roles",
        json={"role": "publisher", "reason": "self escalate"},
        headers=_auth(student),
    )
    assert r.status_code == 403


def test_admin_operations_require_mfa_and_are_audited(client: TestClient, db: Session) -> None:
    owner_email, owner_mfa = _make_owner(client)
    owner_no_mfa = _login(client, owner_email, mfa=False)
    reviewer_token = _login(client, _email())
    reviewer = client.get("/v1/me", headers=_auth(reviewer_token)).json()
    grant_body = {
        "role": "subject_reviewer",
        "scope": {"grade": 11, "subject": "chemistry"},
        "reason": "named reviewer",
    }

    no_mfa = client.post(f"/v1/admin/users/{reviewer['id']}/roles", json=grant_body, headers=_auth(owner_no_mfa))
    assert no_mfa.status_code == 403 and "multi-factor" in no_mfa.json()["detail"]

    granted = client.post(f"/v1/admin/users/{reviewer['id']}/roles", json=grant_body, headers=_auth(owner_mfa))
    assert granted.status_code == 201
    assert client.get("/v1/me", headers=_auth(reviewer_token)).json()["roles"] == ["subject_reviewer"]
    grant_id = granted.json()["id"]
    events = db.scalars(select(AuditEvent).where(AuditEvent.target_id == reviewer["id"])).all()
    assert [e.action for e in events] == ["role.grant"] and events[0].details["scope"]["subject"] == "chemistry"

    revoked = client.post(
        f"/v1/admin/role-grants/{grant_id}/revoke", json={"reason": "left the team"}, headers=_auth(owner_mfa)
    )
    assert revoked.status_code == 200 and revoked.json()["revoked_at"]
    assert client.get("/v1/me", headers=_auth(reviewer_token)).json()["roles"] == []
    db.expire_all()
    grant = db.get(StaffRoleGrant, uuid.UUID(grant_id))
    assert grant is not None and grant.revoke_reason == "left the team"  # history kept, never deleted


def test_admins_cannot_change_their_own_roles_or_grant_student(client: TestClient) -> None:
    _, owner_mfa = _make_owner(client)
    me = client.get("/v1/me", headers=_auth(owner_mfa)).json()
    self_grant = client.post(
        f"/v1/admin/users/{me['id']}/roles",
        json={"role": "publisher", "reason": "self service"},
        headers=_auth(owner_mfa),
    )
    assert self_grant.status_code == 403
    other = client.get("/v1/me", headers=_auth(_login(client, _email()))).json()
    student = client.post(
        f"/v1/admin/users/{other['id']}/roles",
        json={"role": "student", "reason": "not staff"},
        headers=_auth(owner_mfa),
    )
    assert student.status_code == 409
    missing = client.post(
        f"/v1/admin/users/{uuid.uuid4()}/roles",
        json={"role": "publisher", "reason": "nobody"},
        headers=_auth(owner_mfa),
    )
    assert missing.status_code == 404
