"""Application sessions: exchange, use, list, revoke, sign-out, expiry, idle timeout and isolation (P04.S1.T2/T3)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.modules.identity.sessions import UserSession


def _email() -> str:
    return f"session-{uuid.uuid4().hex[:10]}@example.com"


def _jwt(client: TestClient, email: str, mfa: bool = False) -> str:
    client.post("/v1/dev-auth/register", json={"email": email, "password": "correct-horse-battery"})
    r = client.post("/v1/dev-auth/token", json={"email": email, "password": "correct-horse-battery", "mfa": mfa})
    return str(r.json()["access_token"])


def _session(client: TestClient, jwt: str, kind: str = "web", label: str | None = None) -> dict:
    r = client.post(
        "/v1/sessions",
        json={"kind": kind, "device_label": label},
        headers={"Authorization": f"Bearer {jwt}", "User-Agent": "pytest-browser/1.0"},
    )
    assert r.status_code == 201, r.text
    assert r.headers["cache-control"] == "no-store"
    return r.json()


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_exchange_and_use_a_session_token(client: TestClient, db: Session) -> None:
    email = _email()
    created = _session(client, _jwt(client, email), label="Chrome on laptop")
    token = created["session_token"]
    assert token.startswith("pls_") and created["session"]["kind"] == "web"
    me = client.get("/v1/me", headers=_h(token))
    assert me.status_code == 200 and me.json()["email"] == email
    stored = db.scalar(select(UserSession).where(UserSession.id == uuid.UUID(created["session"]["id"])))
    assert stored is not None and token not in stored.token_hash and len(stored.token_hash) == 64


def test_a_session_cannot_mint_another_session(client: TestClient) -> None:
    token = _session(client, _jwt(client, _email()))["session_token"]
    r = client.post("/v1/sessions", json={"kind": "web"}, headers=_h(token))
    assert r.status_code == 403


def test_list_marks_current_and_revocation_is_owner_only(client: TestClient) -> None:
    email = _email()
    jwt = _jwt(client, email)
    web = _session(client, jwt, "web", "Laptop")
    phone = _session(client, jwt, "native", "Phone")
    listed = client.get("/v1/me/sessions", headers=_h(web["session_token"])).json()
    assert {s["id"] for s in listed} >= {web["session"]["id"], phone["session"]["id"]}
    assert [s["current"] for s in listed if s["id"] == web["session"]["id"]] == [True]
    # Another learner cannot see or revoke this learner's session (404, not 403: no existence oracle).
    other = _session(client, _jwt(client, _email()))["session_token"]
    assert client.delete(f"/v1/me/sessions/{phone['session']['id']}", headers=_h(other)).status_code == 404
    assert client.get("/v1/me", headers=_h(phone["session_token"])).status_code == 200
    # The owner revokes the phone session; it stops working immediately.
    assert (
        client.delete(f"/v1/me/sessions/{phone['session']['id']}", headers=_h(web["session_token"])).status_code == 204
    )
    assert client.get("/v1/me", headers=_h(phone["session_token"])).status_code == 401


def test_revoke_others_keeps_the_current_session(client: TestClient) -> None:
    jwt = _jwt(client, _email())
    a, b, c = (_session(client, jwt)["session_token"] for _ in range(3))
    assert client.post("/v1/me/sessions/revoke-others", headers=_h(a)).status_code == 204
    assert client.get("/v1/me", headers=_h(a)).status_code == 200
    assert client.get("/v1/me", headers=_h(b)).status_code == 401
    assert client.get("/v1/me", headers=_h(c)).status_code == 401


def test_sign_out_revokes_only_the_current_session(client: TestClient) -> None:
    jwt = _jwt(client, _email())
    a, b = _session(client, jwt)["session_token"], _session(client, jwt)["session_token"]
    assert client.delete("/v1/me/session", headers=_h(a)).status_code == 204
    assert client.get("/v1/me", headers=_h(a)).status_code == 401
    assert client.get("/v1/me", headers=_h(b)).status_code == 200
    assert client.delete("/v1/me/session", headers=_h(jwt)).status_code == 409  # a provider token is not a session


def test_expired_and_idle_sessions_stop_working(client: TestClient, db: Session) -> None:
    jwt = _jwt(client, _email())
    expired = _session(client, jwt)
    idle = _session(client, jwt)
    now = datetime.now(UTC)
    db.get(UserSession, uuid.UUID(expired["session"]["id"])).expires_at = now - timedelta(seconds=1)
    db.get(UserSession, uuid.UUID(idle["session"]["id"])).last_seen_at = now - timedelta(days=8)
    db.commit()
    assert client.get("/v1/me", headers=_h(expired["session_token"])).status_code == 401
    assert client.get("/v1/me", headers=_h(idle["session_token"])).status_code == 401
    db.expire_all()
    row = db.get(UserSession, uuid.UUID(idle["session"]["id"]))
    assert row is not None and row.revoke_reason == "idle_timeout"
    assert client.get("/v1/me", headers=_h("pls_" + "x" * 43)).status_code == 401  # unknown token


def test_session_inherits_mfa_from_the_provider_token(client: TestClient) -> None:
    email = _email()
    plain = _session(client, _jwt(client, email, mfa=False))["session_token"]
    strong = _session(client, _jwt(client, email, mfa=True))["session_token"]
    assert client.get("/v1/me", headers=_h(plain)).json()["mfa_session"] is False
    assert client.get("/v1/me", headers=_h(strong)).json()["mfa_session"] is True
