"""STAFF-MFA-01: two-step sign-in with an authenticator app. A signed-in session proves the second factor with the
current code and is a multi-factor session for twelve hours; the permission matrix decides which actions need it.
Accounts here are technical fixtures; the codes are computed from the secret the API returned at set-up."""

from __future__ import annotations

import base64
import time
import uuid
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from portal_api.config import ConfigurationError, Role, Settings
from portal_api.modules.audit.models import AuditEvent
from portal_api.modules.identity import mfa
from portal_api.modules.identity.mfa import TotpCredential, TotpRecoveryCode
from portal_api.modules.identity.sessions import UserSession
from tests.test_content_workflow import Staff


def _session(client: TestClient, who: Staff) -> dict[str, str]:
    """A fresh application session (what the website and the app hold), without a second factor."""
    r = client.post("/v1/sessions", headers=who.headers, json={"kind": "web"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['session_token']}"}


def _code(secret: str, ahead: int = 0) -> str:
    key = secret.replace(" ", "")
    raw = base64.b32decode(key + "=" * (-len(key) % 8))
    return mfa.totp(raw, int(time.time()) // mfa.PERIOD_S + ahead)


def _set_up(client: TestClient, headers: dict[str, str]) -> tuple[str, list[str]]:
    started = client.post("/v1/me/mfa/enrol", headers=headers)
    assert started.status_code == 200, started.text
    secret = started.json()["secret"]
    assert started.json()["otpauth_uri"].startswith("otpauth://totp/Sirf%20Concepts%3A")
    done = client.post("/v1/me/mfa/confirm", headers=headers, json={"code": _code(secret)})
    assert done.status_code == 200, done.text
    return secret, done.json()["recovery_codes"]


def _owner(client: TestClient, db: Session) -> Staff:
    return Staff(client, db, ["owner_admin"])


def test_set_up_then_a_code_opens_mfa_actions_for_this_session_only(client: TestClient, db: Session) -> None:
    who = _owner(client, db)
    first = _session(client, who)
    refused = client.get("/v1/admin/staff", headers=first)
    assert refused.status_code == 403 and refused.json()["code_reason"] == "MFA_REQUIRED"
    assert client.get("/v1/me/mfa", headers=first).json() == {
        "enabled": False,
        "session_verified": False,
        "recovery_codes_left": 0,
    }

    secret, recovery = _set_up(client, first)
    assert len(recovery) == 8 and len(set(recovery)) == 8
    assert client.get("/v1/admin/staff", headers=first).status_code == 200  # setting up proved the factor here
    assert client.get("/v1/me", headers=first).json()["mfa_session"] is True
    assert client.get("/v1/me/mfa", headers=first).json() == {
        "enabled": True,
        "session_verified": True,
        "recovery_codes_left": 8,
    }

    # another sign-in starts without it, and the code already used can't be used again
    second = _session(client, who)
    assert client.get("/v1/admin/staff", headers=second).status_code == 403
    replay = client.post("/v1/me/mfa/verify", headers=second, json={"code": _code(secret)})
    assert replay.status_code == 400 and replay.json()["title"] == "INVALID_CODE"
    ok = client.post("/v1/me/mfa/verify", headers=second, json={"code": _code(secret, ahead=1)})
    assert ok.status_code == 200 and ok.json()["session_verified"] is True, ok.text
    assert client.get("/v1/admin/staff", headers=second).status_code == 200

    actions = db.scalars(select(AuditEvent.action).where(AuditEvent.actor_user_id == who.id)).all()
    assert "mfa.enabled" in actions and "mfa.verified" in actions

    # the secret is stored encrypted, the recovery codes as hashes
    stored = db.get(TotpCredential, who.id)
    assert stored is not None and secret.replace(" ", "") not in stored.secret_enc
    hashes = db.scalars(select(TotpRecoveryCode.code_hash).where(TotpRecoveryCode.user_id == who.id)).all()
    assert len(hashes) == 8 and not set(hashes) & {c.replace("-", "") for c in recovery}


def test_the_second_factor_lasts_twelve_hours(client: TestClient, db: Session) -> None:
    who = _owner(client, db)
    headers = _session(client, who)
    _set_up(client, headers)
    assert client.get("/v1/admin/staff", headers=headers).status_code == 200
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == who.id)
        .values(mfa_verified_at=UserSession.mfa_verified_at - timedelta(hours=12, minutes=1))
    )
    db.commit()
    again = client.get("/v1/admin/staff", headers=headers)
    assert again.status_code == 403 and again.json()["code_reason"] == "MFA_REQUIRED"
    assert client.get("/v1/me/mfa", headers=headers).json()["session_verified"] is False


def test_wrong_codes_are_counted_and_lock_checking(client: TestClient, db: Session) -> None:
    who = _owner(client, db)
    headers = _session(client, who)
    secret, _ = _set_up(client, headers)
    other = _session(client, who)
    for _ in range(5):
        r = client.post("/v1/me/mfa/verify", headers=other, json={"code": "000000"})
        assert r.status_code == 400, r.text
    locked = client.post("/v1/me/mfa/verify", headers=other, json={"code": _code(secret, ahead=1)})
    assert locked.status_code == 429 and locked.json()["title"] == "RATE_LIMITED", locked.text
    assert client.get("/v1/admin/staff", headers=other).status_code == 403
    db.execute(update(TotpCredential).where(TotpCredential.user_id == who.id).values(locked_until=None))
    db.commit()
    assert client.post("/v1/me/mfa/verify", headers=other, json={"code": _code(secret, ahead=1)}).status_code == 200


def test_a_recovery_code_works_once_and_turning_off_needs_a_code(client: TestClient, db: Session) -> None:
    who = _owner(client, db)
    headers = _session(client, who)
    _, recovery = _set_up(client, headers)
    other = _session(client, who)
    used = client.post("/v1/me/mfa/verify", headers=other, json={"code": recovery[0].upper()})
    assert used.status_code == 200 and used.json()["recovery_codes_left"] == 7, used.text
    assert client.post("/v1/me/mfa/verify", headers=other, json={"code": recovery[0]}).status_code == 400

    assert client.post("/v1/me/mfa/enrol", headers=headers).status_code == 409  # already set up
    assert client.post("/v1/me/mfa/disable", headers=headers, json={"code": "123456"}).status_code == 400
    assert client.post("/v1/me/mfa/disable", headers=headers, json={"code": recovery[1]}).status_code == 204
    assert client.get("/v1/me/mfa", headers=headers).json() == {
        "enabled": False,
        "session_verified": False,
        "recovery_codes_left": 0,
    }
    for h in (headers, other):  # every session lost the factor
        assert client.get("/v1/admin/staff", headers=h).status_code == 403
    assert client.post("/v1/me/mfa/verify", headers=headers, json={"code": recovery[2]}).status_code == 409
    assert "mfa.disabled" in db.scalars(select(AuditEvent.action).where(AuditEvent.actor_user_id == who.id)).all()


def test_rules_around_set_up(client: TestClient, db: Session) -> None:
    who = Staff(client, db, [])  # anyone may set it up; only the permission matrix asks for it
    headers = _session(client, who)
    assert client.post("/v1/me/mfa/confirm", headers=headers, json={"code": "123456"}).status_code == 409
    assert client.post("/v1/me/mfa/verify", headers=headers, json={"code": "123456"}).status_code == 409
    first = client.post("/v1/me/mfa/enrol", headers=headers).json()["secret"]
    second = client.post("/v1/me/mfa/enrol", headers=headers).json()["secret"]  # an unfinished set-up starts again
    assert first != second
    assert client.post("/v1/me/mfa/confirm", headers=headers, json={"code": _code(first)}).status_code == 400
    assert client.get("/v1/me/mfa", headers=headers).json()["enabled"] is False
    assert client.post("/v1/me/mfa/confirm", headers=headers, json={"code": _code(second)}).status_code == 200
    # an identity-provider token is not a session: there is nothing to step up
    r = client.post("/v1/me/mfa/verify", headers=who.headers, json={"code": _code(second, ahead=1)})
    assert r.status_code == 409 and r.json()["code_reason"] == "SESSION_REQUIRED"
    assert client.get("/v1/me/mfa").status_code == 401
    assert client.post("/v1/me/mfa/verify", headers=headers, json={"code": "12"}).status_code == 422

    # starting set-up needs a recent sign-in (a device left signed in can't add its own authenticator)
    late = Staff(client, db, [])
    old = _session(client, late)
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == late.id)
        .values(created_at=UserSession.created_at - timedelta(minutes=16))
    )
    db.commit()
    stale = client.post("/v1/me/mfa/enrol", headers=old)
    assert stale.status_code == 403 and stale.json()["title"] == "REAUTH_REQUIRED"


def test_an_operator_can_reset_a_lost_authenticator(client: TestClient, db: Session) -> None:
    who = _owner(client, db)
    headers = _session(client, who)
    _set_up(client, headers)
    assert mfa.main(["--email", f"nobody-{uuid.uuid4().hex[:8]}@example.com", "--reason", "fixture"]) == 1
    assert mfa.main(["--email", who.email.upper(), "--reason", "Fixture: lost phone"]) == 0
    assert client.get("/v1/me/mfa", headers=headers).json()["enabled"] is False
    assert client.get("/v1/admin/staff", headers=headers).status_code == 403
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "mfa.reset", AuditEvent.target_id == str(who.id)))
    assert event is not None and event.actor_user_id is None and event.details["via"] == "cli"
    _set_up(client, _session(client, who))  # and it can be set up again


def test_a_session_the_identity_provider_marked_mfa_is_unchanged(client: TestClient, db: Session) -> None:
    who = Staff(client, db, ["owner_admin"], mfa=True)  # the development adapter asserts the factor at sign-in
    headers = _session(client, who)
    assert client.get("/v1/admin/staff", headers=headers).status_code == 200
    assert client.get("/v1/me/mfa", headers=headers).json()["session_verified"] is True


def test_production_needs_its_own_mfa_secret_key() -> None:
    from tests.test_config import OIDC, PROD_DB

    base: dict[str, Any] = {
        "role": Role.production,
        "database_url": PROD_DB,
        "public_api_origin": "https://api.example.org",
        "build_id": "sha-abc123",
        "cors_origins": ["https://app.example.org"],
    }
    for bad in ("dev-only-mfa-secret-key", "too-short"):
        with pytest.raises(ConfigurationError, match="mfa_secret_key"):
            Settings(**{**OIDC, "mfa_secret_key": bad}, **base)
    assert Settings(**OIDC, **base).mfa_secret_key.get_secret_value() == OIDC["mfa_secret_key"]
