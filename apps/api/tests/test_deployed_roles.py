"""Deployed roles: the development identity adapter is absent (routes) and untrusted (tokens), not just undocumented."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from portal_api.config import get_settings
from portal_api.db import reset_engine
from portal_api.modules.identity import tokens


def _clear_caches() -> None:
    """Settings, engine and sessionmaker are process-cached; isolate them so no test inherits another's config."""
    get_settings.cache_clear()
    reset_engine()


DEPLOYED_ENV = {
    "PORTAL_DATABASE_URL": "postgresql+psycopg://portal@db.internal.example:5432/portal",
    "PORTAL_PUBLIC_API_ORIGIN": "https://api.example.org",
    "PORTAL_BUILD_ID": "sha-0123456",
    "PORTAL_CORS_ORIGINS": '["https://example.org"]',
    "PORTAL_DEV_AUTH_ENABLED": "false",
    "PORTAL_OIDC_ISSUER": "https://idp.example.org/pool",
    "PORTAL_OIDC_AUDIENCE": "client-1",
    "PORTAL_EVIDENCE_STORE": "s3",
    "PORTAL_TRIAL_DEVICE_EVIDENCE": "fallback",
    "PORTAL_TRIAL_REF_PEPPER": "deployment-secret-fixture",
    "PORTAL_NOTIFICATION_EMAIL_ADAPTER": "none",  # P15.S1: the dev outbox is refused in deployed roles
}


@pytest.fixture(params=["production", "staging"])
def deployed_client(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    from portal_api.main import create_app

    dev_token = tokens.get_dev_issuer().issue("dev|someone@example.com", "someone@example.com", mfa=True)
    for k, v in DEPLOYED_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("PORTAL_ROLE", request.param)
    _clear_caches()
    try:
        client = TestClient(create_app())
        client.dev_token = dev_token  # type: ignore[attr-defined]
        yield client
    finally:
        monkeypatch.undo()
        _clear_caches()


def test_dev_auth_routes_do_not_exist(deployed_client: TestClient) -> None:
    for path in ("/v1/dev-auth/register", "/v1/dev-auth/token"):
        r = deployed_client.post(path, json={"email": "a@example.com", "password": "correct-horse-battery"})
        assert r.status_code == 404, path
    assert deployed_client.get("/docs").status_code == 404  # interactive docs are development/test only


def test_dev_issued_tokens_are_not_trusted(deployed_client: TestClient) -> None:
    r = deployed_client.get("/v1/me", headers={"Authorization": f"Bearer {deployed_client.dev_token}"})  # type: ignore[attr-defined]
    assert r.status_code == 401


def test_deployed_roles_refuse_to_start_with_the_dev_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    from portal_api.config import ConfigurationError
    from portal_api.main import create_app

    for k, v in DEPLOYED_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("PORTAL_ROLE", "production")
    monkeypatch.setenv("PORTAL_DEV_AUTH_ENABLED", "true")
    _clear_caches()
    try:
        with pytest.raises(ConfigurationError, match="dev_auth_enabled"):
            create_app()
    finally:
        monkeypatch.undo()
        _clear_caches()


def test_deployed_runtime_config_never_offers_dev_sign_in(deployed_client: TestClient) -> None:
    assert deployed_client.get("/v1/runtime-config").json()["sign_in_methods"] == ["oidc"]
