"""P17.S3.T1/T3 (OPS-01): alert signals with thresholds and owners, and audited feature switches that refuse only
new optional work while active attempts carry on."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from portal_api.db import get_sessionmaker
from portal_api.modules.audit.models import AuditEvent
from portal_api.modules.system import operations
from tests.test_attempts import _form, _learner, _start
from tests.test_content_workflow import Staff


def _operator(client: TestClient, mfa: bool = True) -> Staff:
    with get_sessionmaker()() as db:
        return Staff(client, db, ["platform_operator"], mfa=mfa)


def test_signals_report_every_watched_value_with_thresholds(client: TestClient) -> None:
    op = _operator(client)
    assert client.get("/v1/ops/signals", headers=_operator(client, mfa=False).headers).status_code == 403
    r = client.get("/v1/ops/signals", headers=op.headers)
    assert r.status_code == 200, r.text
    names = {s["name"] for s in r.json()}
    assert names == set(operations.THRESHOLDS) | set(operations.UNAVAILABLE)
    runbook = (Path(__file__).resolve().parents[3] / "docs" / "runbooks" / "alerts.md").read_text(encoding="utf-8")
    for s in r.json():
        expected = ("ok", "warn", "alert") if s["available"] else ("unavailable",)
        assert s["level"] in expected and s["owner"] and s["runbook"].startswith("docs/runbooks/alerts.md#")
        assert f"## {s['runbook'].split('#', 1)[1]}\n" in runbook  # every signal links to a real runbook section


def test_switching_new_practice_tests_off_keeps_active_attempts_going(
    client: TestClient, physics: dict[str, Any]
) -> None:
    op = _operator(client)
    learner = _learner(client)
    a = _start(client, learner, _form(client, learner, physics["chapter"]).json()["id"])
    url = "/v1/ops/features/new_practice_tests"
    assert client.put(url, headers=op.headers, json={"enabled": False, "reason": "short"}).status_code == 422
    assert (
        client.put(
            "/v1/ops/features/nope", headers=op.headers, json={"enabled": False, "reason": "Fixture reason"}
        ).status_code
        == 404
    )
    try:
        off = client.put(url, headers=op.headers, json={"enabled": False, "reason": "Fixture: form builder incident"})
        assert off.status_code == 200 and not next(f for f in off.json() if f["key"] == "new_practice_tests")["enabled"]
        refused = _form(client, learner, physics["chapter"])
        assert refused.status_code == 503 and refused.json()["title"] == "FEATURE_DISABLED"
        # The attempt already started carries on: answers save and it can be submitted.
        opt = a["items"][0]["options"][0]["id"]
        saved = client.post(
            f"/v1/attempts/{a['id']}/answers",
            headers=learner.headers,
            json={"ops": [{"op_id": str(uuid.uuid4()), "position": 1, "revision": 1, "option_id": opt}]},
        )
        assert saved.status_code == 200
    finally:
        on = client.put(url, headers=op.headers, json={"enabled": True, "reason": "Fixture: incident resolved"})
        assert on.status_code == 200
    assert _form(client, learner, physics["chapter"]).status_code == 201
    with get_sessionmaker()() as db:
        actions = db.scalars(
            select(AuditEvent.details)
            .where(AuditEvent.action == "ops.feature_switched", AuditEvent.target_id == "new_practice_tests")
            .order_by(AuditEvent.at, AuditEvent.id)
        ).all()
    assert [d["enabled"] for d in actions][-2:] == [False, True]
