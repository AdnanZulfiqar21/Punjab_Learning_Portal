"""P19.S3.T3 (ISOLATION-01): no shared cache can ever hand one person's data to another. Every successful response
from a non-public GET route, for a learner and for staff holding every role, carries `Cache-Control` with `private`
or `no-store`; a sample of routes keyed by an object's id is checked with real objects, and those objects are not
visible to another learner. Searching is private: the words searched for never reach the request log, the audit
trail or analytics, and a signed-in search answers exactly what an anonymous one does. A device another account has
used tells the next account nothing about that account. Built from the live OpenAPI document, so a new route is
covered automatically. Fixture accounts and the development/test device-evidence adapter only."""

from __future__ import annotations

import logging
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from portal_api.main import app
from portal_api.modules.identity.permissions import STAFF_ROLES
from tests.test_attempts import _form, _learner, _start
from tests.test_authorization_matrix import PUBLIC
from tests.test_content_workflow import Staff
from tests.test_trial_claims import _claim, _install, _native, _user


def _private(cache_control: str | None) -> bool:
    cc = (cache_control or "").lower()
    return "private" in cc or "no-store" in cc


def _plain_gets() -> list[str]:
    spec = app.openapi()
    return sorted(p for p, ops in spec["paths"].items() if "get" in ops and "{" not in p and f"GET {p}" not in PUBLIC)


def test_every_personal_response_is_private_to_shared_caches(client: TestClient, db: Session) -> None:
    learner = _learner(client)
    staff = Staff(client, db, [r.value for r in STAFF_ROLES], mfa=True)
    paths = _plain_gets()
    assert len(paths) > 30  # the sweep really covers the personal and staff surface
    leaks, answered = [], 0
    for who in (learner, staff):
        for path in paths:
            r = client.get(path, headers=who.headers)
            if r.status_code < 300:
                answered += 1
                if not _private(r.headers.get("cache-control")):
                    leaks.append(f"{path}: {r.headers.get('cache-control')!r}")
    assert answered > 30
    assert leaks == [], "; ".join(leaks)


def test_personal_objects_are_private_and_never_cross_accounts(client: TestClient, physics: dict[str, Any]) -> None:
    owner, other = _learner(client), _learner(client)
    form = _form(client, owner, physics["chapter"], count=2).json()
    attempt = _start(client, owner, form["id"])
    url = f"/v1/attempts/{attempt['id']}"
    mine = client.get(url, headers=owner.headers)
    assert mine.status_code == 200 and _private(mine.headers.get("cache-control"))
    assert client.get(url, headers=other.headers).status_code == 404  # never another learner's attempt
    submit = client.post(
        f"{url}/submit", headers=owner.headers, json={"idempotency_key": "isolation-check-0001", "ops": []}
    )
    assert submit.status_code == 200
    result = client.get(f"{url}/result", headers=owner.headers)
    assert result.status_code == 200 and _private(result.headers.get("cache-control"))
    assert client.get(f"{url}/result", headers=other.headers).status_code == 404


def test_search_terms_are_never_recorded(client: TestClient, db: Session, caplog: pytest.LogCaptureFixture) -> None:
    learner = _learner(client)
    term = "isolationsentinelterm"
    with caplog.at_level(logging.DEBUG):
        for path in (f"/v1/search?q={term}", f"/v1/help/articles?q={term}"):
            signed_in = client.get(path, headers=learner.headers)
            assert signed_in.status_code == 200
            assert signed_in.json() == client.get(path).json()  # nothing personal, so a shared cache key is safe
    server = [r for r in caplog.records if not r.name.startswith("httpx")]  # the test client logs its own URLs
    assert server and term not in " | ".join(f"{r.getMessage()} {r.__dict__}" for r in server)
    for sql in (
        "select count(*) from audit_event where details::text like :t",
        "select count(*) from analytics_event where properties::text like :t",
    ):
        assert db.execute(text(sql), {"t": f"%{term}%"}).scalar_one() == 0


def test_a_shared_device_discloses_nothing_about_the_other_account(client: TestClient) -> None:
    first, second, install = _user(client), _user(client), _install()
    granted = _claim(client, first, install).json()
    assert granted["state"] == "granted" and granted["device_id"]
    refused = _claim(client, second, install, verdict="consumed")
    assert refused.status_code == 200 and refused.json()["state"] == "device_used"
    devices = client.get("/v1/me/trial/devices", headers={**second.headers, **_native(install)})
    access = client.get("/v1/me/access", headers={**second.headers, **_native(install)})
    assert devices.status_code == 200 and access.status_code == 200
    for body in (refused.text, devices.text, access.text):
        for secret in (str(first.id), first.email, granted["device_id"]):
            assert secret not in body
