"""P04.S3.T3 (REAUTH-01): downloading all your data or asking to delete your account needs a recent sign-in.

A sign-in within the last 15 minutes is enough; an older app session or an older provider token is refused with
REAUTH_REQUIRED and works again after signing in. Everything else keeps working on the older session. Accounts are
labelled technical fixtures.
"""

from __future__ import annotations

import time
import uuid

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from portal_api.modules.identity import tokens
from tests.test_content_workflow import Staff
from tests.test_sessions import _h, _session


def _token(client: TestClient, who: Staff) -> str:
    return str(who.headers["Authorization"].split(" ", 1)[1])


def _deletion(client: TestClient, headers: dict[str, str], email: str) -> int:
    r = client.post("/v1/me/deletion-request", headers=headers, json={"confirm_email": email, "reason": "Fixture"})
    return r.status_code


def test_export_and_deletion_need_a_sign_in_in_the_last_15_minutes(client: TestClient) -> None:
    with get_sessionmaker()() as db:
        who = Staff(client, db, [])
    old = _session(client, _token(client, who))["session_token"]
    with get_sessionmaker()() as db:  # this session was signed in 20 minutes ago
        db.execute(
            text("update user_session set created_at = now() - interval '20 minutes' where user_id = :u"),
            {"u": str(who.id)},
        )
        db.commit()
    export = client.get("/v1/me/data-export", headers=_h(old))
    assert export.status_code == 403 and export.json()["title"] == "REAUTH_REQUIRED"
    assert "sign in again" in export.json()["detail"]
    assert _deletion(client, _h(old), who.email) == 403
    assert client.get("/v1/me", headers=_h(old)).status_code == 200  # everything else keeps working

    # A provider token issued long ago (but not expired) is refused the same way.
    issuer = tokens.get_dev_issuer()
    now = int(time.time())
    with get_sessionmaker()() as db:
        subject = db.execute(text("select subject from app_user where id = :u"), {"u": str(who.id)}).scalar_one()
    stale = jwt.encode(
        {
            "iss": issuer.issuer,
            "aud": issuer.audience,
            "sub": subject,
            "iat": now - 3600,
            "exp": now + 600,
            "jti": uuid.uuid4().hex,
            "token_use": "access",
            "amr": ["pwd"],
            "email": who.email,
        },
        issuer._key,
        algorithm="RS256",
        headers={"kid": issuer.kid},
    )
    assert client.get("/v1/me", headers=_h(stale)).status_code == 200
    assert client.get("/v1/me/data-export", headers=_h(stale)).status_code == 403

    # Signing in again (a new session, or a fresh token) is enough.
    fresh = _session(client, _token(client, who))["session_token"]
    assert client.get("/v1/me/data-export", headers=_h(fresh)).status_code == 200
    assert _deletion(client, _h(fresh), who.email) == 202
