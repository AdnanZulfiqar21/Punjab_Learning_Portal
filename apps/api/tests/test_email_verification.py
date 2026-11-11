"""AUTH-PASSWORD-01: the portal's own sign-up with a 6-digit email code (Resend in deployed roles).

Uses the development outbox (no email leaves the machine) and a stubbed Resend endpoint. Nothing here is evidence that
a real Resend account, domain or inbox works: that needs the owner's key and a verified domain (BLOCKERS B04).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
import uuid
from collections.abc import Iterator
from datetime import timedelta
from io import BytesIO
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from portal_api import email
from portal_api.config import ConfigurationError, Role, Settings, get_settings
from portal_api.db import reset_engine
from portal_api.modules.audit.models import AuditEvent
from portal_api.modules.identity import password_auth, tokens
from portal_api.modules.identity.models import AppUser, EmailCode, PasswordCredential

PASSWORD = "correct-horse-battery"
DOB = "2008-05-14"  # a technical fixture value
NAMES = {"first_name": "Test", "surname": "Learner"}  # technical fixture values


def _email() -> str:
    return f"signup-{uuid.uuid4().hex[:10]}@example.com"


def _codes(address: str) -> list[str]:
    out = []
    for entry in email.outbox():
        if entry.message.to == address and entry.message.tag == "verify-email":
            found = re.search(r"\b(\d{6})\b", entry.message.text)
            assert found
            out.append(found.group(1))
    return out


def _register(client: TestClient, address: str, password: str = PASSWORD) -> None:
    r = client.post(
        "/v1/auth/register",
        json={"email": address, "password": password, "phone": "0300 1234567", "date_of_birth": DOB, **NAMES},
    )
    assert r.status_code == 202, r.text


def _age_codes(db: Session, address: str, by: timedelta) -> None:
    """Move this account's codes into the past (instead of waiting) to pass a cooldown or reach an expiry."""
    user_id = db.scalar(select(PasswordCredential.user_id).where(PasswordCredential.email == address))
    db.execute(
        update(EmailCode)
        .where(EmailCode.user_id == user_id)
        .values(created_at=EmailCode.created_at - by, expires_at=EmailCode.expires_at - by)
    )
    db.commit()


# ------------------------------------------------------------------ the whole journey
def test_sign_up_needs_the_emailed_code_then_signs_in(client: TestClient, db: Session) -> None:
    address = _email()
    _register(client, address)
    [code] = _codes(address)
    assert "Sirf Concepts" in email.outbox()[-1].message.subject
    # Can't sign in yet; the right password says so, a wrong one doesn't.
    blocked = client.post("/v1/auth/token", json={"email": address, "password": PASSWORD})
    assert blocked.status_code == 403 and blocked.json()["title"] == "EMAIL_NOT_VERIFIED"
    assert client.post("/v1/auth/token", json={"email": address, "password": "wrong-password"}).status_code == 401
    # The code signs in and the token makes an app session like any identity provider's.
    ok = client.post("/v1/auth/verify-email", json={"email": address.upper(), "code": code})
    assert ok.status_code == 200, ok.text
    session = client.post(
        "/v1/sessions",
        json={"kind": "web", "device_label": "test"},
        headers={"Authorization": f"Bearer {ok.json()['access_token']}"},
    )
    assert session.status_code == 201, session.text
    me = client.get("/v1/me", headers={"Authorization": f"Bearer {session.json()['session_token']}"})
    assert me.status_code == 200 and me.json()["email"] == address
    assert me.json()["phone"] == "+923001234567"  # stored in E.164, not verified
    assert me.json()["date_of_birth"] == DOB
    assert (me.json()["first_name"], me.json()["surname"], me.json()["display_name"]) == (
        "Test",
        "Learner",
        "Test Learner",
    )
    assert not [c for c in me.json()["consents"] if c["document"] == "marketing_messages"]  # no opt-in, no consent
    # Afterwards the password signs in, and the used code can't be used again.
    assert client.post("/v1/auth/token", json={"email": address, "password": PASSWORD}).status_code == 200
    assert client.post("/v1/auth/verify-email", json={"email": address, "code": code}).status_code == 400
    user = db.scalar(select(AppUser).where(AppUser.email == address))
    assert user is not None and user.issuer == get_settings().password_auth_issuer and user.subject.startswith("pwd|")
    actions = set(db.scalars(select(AuditEvent.action).where(AuditEvent.target_id == str(user.id))))
    assert {"account.register", "account.email_verified"} <= actions
    # Only a hash of the code is stored.
    assert all(code not in row.code_hash for row in db.scalars(select(EmailCode).where(EmailCode.user_id == user.id)))


def test_answers_do_not_reveal_which_emails_have_accounts(client: TestClient) -> None:
    taken = _email()
    _register(client, taken)
    client.post("/v1/auth/verify-email", json={"email": taken, "code": _codes(taken)[-1]})
    sent_before = len(email.outbox())
    again = client.post(
        "/v1/auth/register",
        json={"email": taken, "password": "another-password-x", "phone": "03001234567", "date_of_birth": DOB, **NAMES},
    )
    fresh = client.post(
        "/v1/auth/register",
        json={"email": _email(), "password": PASSWORD, "phone": "03001234567", "date_of_birth": DOB, **NAMES},
    )
    assert again.status_code == fresh.status_code == 202 and again.json() == fresh.json()
    assert len(email.outbox()) == sent_before + 1  # only the new address got a code
    # A verified account keeps its password.
    assert client.post("/v1/auth/token", json={"email": taken, "password": PASSWORD}).status_code == 200
    unknown = client.post("/v1/auth/verify-email", json={"email": _email(), "code": "123456"})
    wrong = client.post("/v1/auth/verify-email", json={"email": taken, "code": "000000"})
    assert unknown.status_code == wrong.status_code == 400 and unknown.json()["detail"] == wrong.json()["detail"]
    assert client.post("/v1/auth/resend-code", json={"email": _email()}).status_code == 202


def test_registering_again_before_verifying_replaces_the_password(client: TestClient, db: Session) -> None:
    address = _email()
    _register(client, address, "first-password-1")
    _age_codes(db, address, timedelta(minutes=2))
    _register(client, address, "second-password-2")
    codes = _codes(address)
    assert len(codes) == 2
    # Only the newest code counts.
    if codes[0] != codes[1]:
        assert client.post("/v1/auth/verify-email", json={"email": address, "code": codes[0]}).status_code == 400
    assert client.post("/v1/auth/verify-email", json={"email": address, "code": codes[1]}).status_code == 200
    assert client.post("/v1/auth/token", json={"email": address, "password": "first-password-1"}).status_code == 401
    assert client.post("/v1/auth/token", json={"email": address, "password": "second-password-2"}).status_code == 200


def test_five_wrong_tries_spend_the_code(client: TestClient) -> None:
    address = _email()
    _register(client, address)
    [code] = _codes(address)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(password_auth.MAX_TRIES):
        assert client.post("/v1/auth/verify-email", json={"email": address, "code": wrong}).status_code == 400
    assert client.post("/v1/auth/verify-email", json={"email": address, "code": code}).status_code == 400


def test_codes_expire(client: TestClient, db: Session) -> None:
    address = _email()
    _register(client, address)
    [code] = _codes(address)
    _age_codes(db, address, password_auth.CODE_TTL + timedelta(seconds=1))
    assert client.post("/v1/auth/verify-email", json={"email": address, "code": code}).status_code == 400


def test_new_codes_are_limited(client: TestClient, db: Session) -> None:
    address = _email()
    _register(client, address)
    soon = client.post("/v1/auth/resend-code", json={"email": address})
    assert soon.status_code == 429 and 0 < soon.json()["retry_after"] <= 60
    for _ in range(password_auth.MAX_CODES_PER_HOUR - 1):
        _age_codes(db, address, timedelta(seconds=61))
        assert client.post("/v1/auth/resend-code", json={"email": address}).status_code == 202
    _age_codes(db, address, timedelta(seconds=61))
    capped = client.post("/v1/auth/resend-code", json={"email": address})
    assert capped.status_code == 429 and capped.json()["retry_after"] > 60
    assert len(_codes(address)) == password_auth.MAX_CODES_PER_HOUR
    # The newest code still works.
    ok = client.post("/v1/auth/verify-email", json={"email": address, "code": _codes(address)[-1]})
    assert ok.status_code == 200


def test_validation(client: TestClient) -> None:
    ph = "03001234567"
    assert (
        client.post("/v1/auth/register", json={"email": _email(), "password": "short", "phone": ph}).status_code == 422
    )
    bad_email = {"email": "not-an-email", "password": PASSWORD, "phone": ph}
    assert client.post("/v1/auth/register", json=bad_email).status_code == 422
    # The phone number is required and must look like a mobile number.
    no_phone = {"email": _email(), "password": PASSWORD, "date_of_birth": DOB, **NAMES}
    assert client.post("/v1/auth/register", json=no_phone).status_code == 422
    for bad in ("12345", "0300 123", "+92 21 1234567", "phone"):
        r = client.post(
            "/v1/auth/register",
            json={"email": _email(), "password": PASSWORD, "phone": bad, "date_of_birth": DOB, **NAMES},
        )
        assert r.status_code == 422, bad
    # The date of birth is required and must be plausible.
    no_dob = {"email": _email(), "password": PASSWORD, "phone": ph}
    assert client.post("/v1/auth/register", json=no_dob).status_code == 422
    for bad in ("2999-01-01", "1900-01-01", "2024-01-01", "14-05-2008"):
        r = client.post(
            "/v1/auth/register", json={"email": _email(), "password": PASSWORD, "phone": ph, "date_of_birth": bad}
        )
        assert r.status_code == 422, bad
    for bad in ("12345", "1234567", "abcdef"):
        assert client.post("/v1/auth/verify-email", json={"email": _email(), "code": bad}).status_code == 422


def test_dev_shortcut_reads_the_outbox_code(client: TestClient) -> None:
    address = _email()
    _register(client, address)
    r = client.post("/v1/dev-auth/last-code", json={"email": address})
    assert r.status_code == 200 and r.json()["code"] == _codes(address)[-1]


# ------------------------------------------------------------------ provider failures (DEGRADATION-01)
@pytest.fixture
def no_email_sender(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("PORTAL_NOTIFICATION_EMAIL_ADAPTER", "none")
    get_settings.cache_clear()
    yield
    monkeypatch.undo()
    get_settings.cache_clear()


def test_a_code_that_could_not_be_sent_is_reported_and_removed(
    client: TestClient, db: Session, no_email_sender: None
) -> None:
    address = _email()
    r = client.post(
        "/v1/auth/register",
        json={"email": address, "password": PASSWORD, "phone": "03001234567", "date_of_birth": DOB, **NAMES},
    )
    assert r.status_code == 503 and r.json()["code_reason"] == "EMAIL_UNAVAILABLE"
    user_id = db.scalar(select(PasswordCredential.user_id).where(PasswordCredential.email == address))
    assert user_id is not None
    assert db.scalar(select(EmailCode.id).where(EmailCode.user_id == user_id)) is None


# ------------------------------------------------------------------ the Resend adapter
class _FakeResponse:
    def __init__(self, body: dict[str, Any]) -> None:
        self._body = json.dumps(body).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *a: object) -> None:
        return None


@pytest.fixture
def resend_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[urllib.request.Request]]:
    monkeypatch.setenv("PORTAL_NOTIFICATION_EMAIL_ADAPTER", "resend")
    monkeypatch.setenv("PORTAL_RESEND_API_KEY", "re_test_not_a_real_key")
    monkeypatch.setenv("PORTAL_EMAIL_FROM", "Sirf Concepts <no-reply@example.com>")
    get_settings.cache_clear()
    calls: list[urllib.request.Request] = []
    yield calls
    monkeypatch.undo()
    get_settings.cache_clear()


def test_resend_request_shape(resend_settings: list[urllib.request.Request], monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(req: urllib.request.Request, timeout: float) -> _FakeResponse:
        resend_settings.append(req)
        return _FakeResponse({"id": "email-123"})

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    msg = email.Message(to="a@example.com", subject="S", text="T 123456", html="<p>T</p>", tag="verify-email")
    result = email.send(msg, idempotency_key="email-code-x")
    assert result.status == "sent" and result.ref == "email-123"
    [req] = resend_settings
    assert req.full_url == "https://api.resend.com/emails" and req.get_method() == "POST"
    headers = {k.lower(): v for k, v in req.header_items()}
    assert headers["authorization"] == "Bearer re_test_not_a_real_key"
    assert headers["idempotency-key"] == "email-code-x"
    body = json.loads(req.data)  # type: ignore[arg-type]
    assert body["from"] == "Sirf Concepts <no-reply@example.com>" and body["to"] == ["a@example.com"]
    assert body["subject"] == "S" and body["text"] == "T 123456"


@pytest.mark.parametrize(("status", "retryable"), [(422, False), (403, False), (429, True), (500, True)])
def test_resend_refusals_are_failures(
    resend_settings: list[urllib.request.Request], monkeypatch: pytest.MonkeyPatch, status: int, retryable: bool
) -> None:
    def fake(req: urllib.request.Request, timeout: float) -> _FakeResponse:
        raise urllib.error.HTTPError(req.full_url, status, "x", {}, BytesIO(b'{"message": "refused"}'))  # type: ignore[arg-type]

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    msg = email.Message(to="a@example.com", subject="S", text="T", html="T", tag="verify-email")
    result = email.send(msg)
    assert result.status == "failed" and result.retryable is retryable and "refused" in (result.error or "")


def test_resend_unreachable_is_retryable(
    resend_settings: list[urllib.request.Request], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(req: urllib.request.Request, timeout: float) -> _FakeResponse:
        raise urllib.error.URLError("no route")

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    msg = email.Message(to="a@example.com", subject="S", text="T", html="T", tag="verify-email")
    assert email.send(msg).retryable is True


# ------------------------------------------------------------------ configuration (deployed roles)
def _pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()


DEPLOYED: dict[str, Any] = {
    "role": Role.production,
    "database_url": "postgresql+psycopg://app@db.internal.example:5432/portal",
    "public_api_origin": "https://api.example.org",
    "build_id": "sha-abc",
    "cors_origins": ["https://example.org"],
    "dev_auth_enabled": False,
    "evidence_store": "s3",
    "evidence_s3_endpoint": "https://s3.internal.example",
    "evidence_s3_bucket": "portal-evidence",
    "evidence_s3_access_key": "deployed-access",
    "evidence_s3_secret_key": "deployed-secret-value",  # pragma: allowlist secret
    "trial_device_evidence": "fallback",
    "trial_ref_pepper": "deployment-secret-fixture",
    "upload_scanner": "clamd",
    "password_auth_issuer": "https://api.example.org/auth",
    "notification_email_adapter": "resend",
    "resend_api_key": "re_deployed_fixture",
    "email_from": "Sirf Concepts <no-reply@example.org>",
}


def test_production_password_auth_configuration() -> None:
    Settings(**DEPLOYED, password_auth_signing_key=_pem())  # complete: no OIDC issuer needed
    with pytest.raises(ConfigurationError, match="password_auth_signing_key"):
        Settings(**DEPLOYED)
    with pytest.raises(ConfigurationError, match="development issuer"):
        Settings(**{**DEPLOYED, "password_auth_issuer": "urn:portal:dev-local-issuer"}, password_auth_signing_key="k")
    with pytest.raises(ConfigurationError, match="email sender"):
        Settings(**{**DEPLOYED, "notification_email_adapter": "none"}, password_auth_signing_key="k")
    with pytest.raises(ConfigurationError, match="resend_api_key"):
        Settings(**{**DEPLOYED, "resend_api_key": ""}, password_auth_signing_key="k")
    with pytest.raises(ConfigurationError, match=r"resend.dev"):
        Settings(**{**DEPLOYED, "email_from": "onboarding@resend.dev"}, password_auth_signing_key="k")
    # Deployed analytics never treat real learners (password issuer) as test accounts.
    s = Settings(**DEPLOYED, password_auth_signing_key=_pem())
    assert s.test_account_issuer != s.password_auth_issuer
    assert Settings().test_account_issuer == Settings().password_auth_issuer  # development: local accounts are tests
    with pytest.raises(ConfigurationError, match="resend"):
        Settings(notification_email_adapter="resend")  # development too: a key and sender are needed


def test_a_configured_signing_key_survives_restarts(monkeypatch: pytest.MonkeyPatch) -> None:
    pem = _pem()
    first = tokens.LocalIssuer("https://api.example.org/auth", "portal-api", 900, pem)
    second = tokens.LocalIssuer("https://api.example.org/auth", "portal-api", 900, pem)
    assert first.public_pem == second.public_pem and first.kid == second.kid
    with pytest.raises(RuntimeError, match="RSA"):
        small = rsa.generate_private_key(public_exponent=65537, key_size=1024)  # noqa: S505 (must be refused)
        tokens.LocalIssuer(
            "i",
            "a",
            1,
            small.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
            ).decode(),
        )


def test_deployed_app_mounts_sign_up_but_not_the_dev_shortcuts(monkeypatch: pytest.MonkeyPatch) -> None:
    from portal_api.main import create_app

    dev_token = tokens.get_local_issuer().issue("dev|someone@example.com", "someone@example.com")
    env = {
        "PORTAL_ROLE": "production",
        "PORTAL_DATABASE_URL": DEPLOYED["database_url"],
        "PORTAL_PUBLIC_API_ORIGIN": DEPLOYED["public_api_origin"],
        "PORTAL_BUILD_ID": "sha-0123456",
        "PORTAL_CORS_ORIGINS": '["https://example.org"]',
        "PORTAL_DEV_AUTH_ENABLED": "false",
        "PORTAL_EVIDENCE_STORE": "s3",
        "PORTAL_EVIDENCE_S3_ENDPOINT": DEPLOYED["evidence_s3_endpoint"],
        "PORTAL_EVIDENCE_S3_BUCKET": DEPLOYED["evidence_s3_bucket"],
        "PORTAL_EVIDENCE_S3_ACCESS_KEY": DEPLOYED["evidence_s3_access_key"],
        "PORTAL_EVIDENCE_S3_SECRET_KEY": DEPLOYED["evidence_s3_secret_key"],
        "PORTAL_TRIAL_DEVICE_EVIDENCE": "fallback",
        "PORTAL_TRIAL_REF_PEPPER": "deployment-secret-fixture",
        "PORTAL_UPLOAD_SCANNER": "clamd",
        "PORTAL_PASSWORD_AUTH_ISSUER": DEPLOYED["password_auth_issuer"],
        "PORTAL_PASSWORD_AUTH_SIGNING_KEY": _pem(),
        "PORTAL_NOTIFICATION_EMAIL_ADAPTER": "resend",
        "PORTAL_RESEND_API_KEY": "re_deployed_fixture",
        "PORTAL_EMAIL_FROM": DEPLOYED["email_from"],
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    reset_engine()
    tokens.reset_local_issuer()
    try:
        client = TestClient(create_app())
        for path in ("/v1/auth/register", "/v1/auth/verify-email", "/v1/auth/resend-code", "/v1/auth/token"):
            assert client.post(path, json={}).status_code == 422, path  # mounted (the body is checked first)
        for path in ("/v1/dev-auth/register", "/v1/dev-auth/token", "/v1/dev-auth/last-code"):
            assert client.post(path, json={}).status_code == 404, path
        with pytest.raises(tokens.InvalidToken):  # a development token is untrusted there
            tokens.verify(dev_token)
        prod_token = tokens.get_local_issuer().issue("pwd|abc", "x@example.org")
        assert tokens.verify(prod_token).issuer == "https://api.example.org/auth"
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
        reset_engine()
        tokens.reset_local_issuer()


@pytest.mark.parametrize(
    ("typed", "stored"),
    [
        ("0300 1234567", "+923001234567"),
        ("0300-1234567", "+923001234567"),
        ("923001234567", "+923001234567"),
        ("+92 (300) 123-4567", "+923001234567"),
        ("0092 300 1234567", "+923001234567"),
        ("+44 7700 900123", "+447700900123"),
    ],
)
def test_phone_numbers_are_stored_in_one_format(typed: str, stored: str) -> None:
    from portal_api.modules.identity.schemas import normalize_phone

    assert normalize_phone(typed) == stored


def test_promotional_emails_need_the_opt_in(client: TestClient) -> None:
    address = _email()
    body = {"email": address, "password": PASSWORD, "phone": "03001234567", "date_of_birth": DOB, **NAMES}
    assert client.post("/v1/auth/register", json={**body, "marketing_emails": True}).status_code == 202
    token = client.post("/v1/auth/verify-email", json={"email": address, "code": _codes(address)[-1]}).json()
    me = client.get("/v1/me", headers={"Authorization": f"Bearer {token['access_token']}"}).json()
    [consent] = [c for c in me["consents"] if c["document"] == "marketing_messages"]
    assert consent["version"] == password_auth.MARKETING_CONSENT_VERSION and consent["withdrawn_at"] is None
    # It can be withdrawn at any time.
    headers = {"Authorization": f"Bearer {token['access_token']}"}
    assert client.delete("/v1/me/consents/marketing_messages", headers=headers).status_code == 204
    me = client.get("/v1/me", headers=headers).json()
    assert all(c["withdrawn_at"] for c in me["consents"] if c["document"] == "marketing_messages")


def test_registering_again_before_verifying_updates_the_opt_in(client: TestClient, db: Session) -> None:
    address = _email()
    body = {"email": address, "password": PASSWORD, "phone": "03001234567", "date_of_birth": DOB, **NAMES}
    client.post("/v1/auth/register", json={**body, "marketing_emails": True})
    client.post("/v1/auth/register", json={**body, "marketing_emails": False, "date_of_birth": "2007-01-02"})
    user = db.scalar(select(AppUser).where(AppUser.email == address))
    assert user is not None and str(user.date_of_birth) == "2007-01-02"
    from portal_api.modules.identity.models import ConsentRecord

    rows = db.scalars(select(ConsentRecord).where(ConsentRecord.user_id == user.id)).all()
    assert rows and all(r.withdrawn_at is not None for r in rows)


def test_names_required_and_tidied(client: TestClient, db: Session) -> None:
    base = {"email": _email(), "password": PASSWORD, "phone": "03001234567", "date_of_birth": DOB}
    for missing in ("first_name", "surname"):
        body = {**base, **NAMES}
        del body[missing]
        assert client.post("/v1/auth/register", json=body).status_code == 422, missing
    for bad in ("", "   ", "R2D2", "<b>x</b>", "a@b", "-x"):
        r = client.post("/v1/auth/register", json={**base, "first_name": bad, "surname": "Learner"})
        assert r.status_code == 422, bad
    address = _email()
    r = client.post(
        "/v1/auth/register",
        json={**base, "email": address, "first_name": "  Muhammad   Ali ", "surname": "O'Neil-Khan"},
    )
    assert r.status_code == 202, r.text
    user = db.scalar(select(AppUser).where(AppUser.email == address))
    assert user is not None
    assert (user.first_name, user.surname, user.display_name) == (
        "Muhammad Ali",
        "O'Neil-Khan",
        "Muhammad Ali O'Neil-Khan",
    )
    # Names in Urdu script are letters too.
    r = client.post("/v1/auth/register", json={**base, "email": _email(), "first_name": "علی", "surname": "خان"})
    assert r.status_code == 202, r.text
