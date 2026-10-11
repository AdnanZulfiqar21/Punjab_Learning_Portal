"""P18.S2.T3 (EXPOSURE-01): runtime configuration, health, error bodies and logs never carry credentials or
deployment secrets. Sentinel values only."""

from __future__ import annotations

import logging
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from portal_api.config import get_settings

SENTINEL_PASSWORD = "Sentinel-pw-" + uuid.uuid4().hex  # pragma: allowlist secret
SENTINEL_TOKEN = "sentinel.token." + uuid.uuid4().hex


def _secrets() -> list[str]:
    s = get_settings()
    db_password = s.database_url.split("://", 1)[1].split("@", 1)[0].split(":", 1)[-1]
    return [s.database_url, db_password, s.trial_ref_pepper]


def test_public_runtime_responses_carry_no_secret(client: TestClient) -> None:
    secrets = _secrets()
    for path in ("/v1/runtime-config", "/healthz", "/readyz", "/v1/does-not-exist"):
        body = client.get(path).text
        assert not [x for x in secrets if x and x in body], path
    bad = client.post("/v1/dev-auth/token", json={"email": "nobody@example.invalid", "password": SENTINEL_PASSWORD})
    assert bad.status_code in (401, 422) and SENTINEL_PASSWORD not in bad.text  # never echoed back
    invalid = client.post("/v1/dev-auth/token", json={"email": 5, "password": SENTINEL_PASSWORD})
    assert invalid.status_code == 422 and SENTINEL_PASSWORD not in invalid.text  # validation errors omit input


def test_an_unexpected_error_shows_no_detail(client: TestClient) -> None:
    app: FastAPI = client.app  # type: ignore[assignment]
    path = f"/v1/__exposure_probe_{uuid.uuid4().hex}"

    def boom() -> None:
        raise RuntimeError(f"connect failed: {get_settings().database_url}")

    app.add_api_route(path, boom, include_in_schema=False)
    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.get(path)
        assert r.status_code == 500
        assert not [x for x in _secrets() if x in r.text] and "Traceback" not in r.text
    finally:
        app.router.routes = [rt for rt in app.router.routes if getattr(rt, "path", None) != path]


def test_logs_carry_no_password_or_bearer_token(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        client.post("/v1/dev-auth/token", json={"email": "nobody@example.invalid", "password": SENTINEL_PASSWORD})
        client.get("/v1/me", headers={"Authorization": f"Bearer {SENTINEL_TOKEN}"})
        client.get(f"/v1/runtime-config?token={SENTINEL_TOKEN}")
    server = [r for r in caplog.records if not r.name.startswith("httpx")]  # the test client logs its own URLs
    assert server  # the request log did run
    text = " | ".join(f"{r.getMessage()} {r.__dict__}" for r in server)  # structured extras included
    assert SENTINEL_PASSWORD not in text and SENTINEL_TOKEN not in text
