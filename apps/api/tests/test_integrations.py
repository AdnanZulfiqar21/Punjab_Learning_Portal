"""P16.S3.T2 (INTEGRATIONS-01): one operator view of every provider: mode, blocker, safe health, usage, budget levels;
never secrets. Fixture settings only."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from portal_api.config import get_settings
from portal_api.modules.system import integrations
from tests.test_content_workflow import Staff


def test_operators_see_every_provider_without_secrets(client: TestClient, db: Session) -> None:
    url = "/v1/ops/integrations"
    assert client.get(url, headers=Staff(client, db, ["platform_operator"]).headers).status_code == 403  # MFA
    assert client.get(url, headers=Staff(client, db, ["owner_admin"], mfa=True).headers).status_code == 403
    r = client.get(url, headers=Staff(client, db, ["platform_operator"], mfa=True).headers)
    assert r.status_code == 200 and r.headers["cache-control"] == "private, no-store"
    rows = {x["key"]: x for x in r.json()}
    assert {"identity", "email", "push", "object_storage", "upload_scanner", "payments", "media"} <= set(rows)
    assert rows["payments"]["mode"] == "unavailable" and rows["payments"]["blocker"] == "B06"
    assert rows["identity"]["mode"] == "development"  # the test role runs the development issuer
    assert rows["object_storage"]["health"] == "ok"
    s = get_settings()
    for secret in (s.trial_ref_pepper, s.database_url):
        assert secret not in r.text


def test_budget_levels() -> None:
    assert integrations._level(79, 100) == (0.79, "ok")
    assert integrations._level(80, 100) == (0.8, "warn")
    assert integrations._level(100, 100) == (1.0, "alert")
    assert integrations._level(5, None) == (None, "ok")
