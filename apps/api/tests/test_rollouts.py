"""P16.S3.T1 (ROLLOUT-01): rollout flags by environment and cohort, with audited changes and a runtime snapshot for the
release record. A flag only ever *restricts* (hides a feature or refuses its entry routes); it never bypasses a
permission, scoring or publication rule. Emergency switches (OPS-01) stay separate. Fixture accounts only."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from portal_api.db import get_sessionmaker
from portal_api.modules.audit.models import AuditEvent
from tests.test_attempts import _learner
from tests.test_operations import _operator

URL = "/v1/ops/rollouts"


def _set(client: TestClient, who: Any, key: str, percent: int, reason: str = "Fixture: staged rollout check") -> Any:
    return client.put(f"{URL}/{key}", headers=who.headers, json={"percent": percent, "reason": reason})


def test_a_rollout_restricts_a_feature_to_a_stable_cohort(client: TestClient) -> None:
    op = _operator(client)
    learner = _learner(client)
    assert client.get("/v1/me/features", headers=learner.headers).json()["study_tools"] is True  # default: everyone
    assert client.get("/v1/me/notes", headers=learner.headers).status_code == 200

    off = _set(client, op, "study_tools", 0)
    assert off.status_code == 200, off.text
    try:
        assert client.get("/v1/me/features", headers=learner.headers).json()["study_tools"] is False
        refused = client.get("/v1/me/notes", headers=learner.headers)
        assert refused.status_code == 404 and refused.json()["code_reason"] == "FEATURE_NOT_AVAILABLE"

        assert _set(client, op, "study_tools", 50).status_code == 200
        learners = [_learner(client) for _ in range(24)]
        seen = [client.get("/v1/me/features", headers=w.headers).json()["study_tools"] for w in learners]
        again = [client.get("/v1/me/features", headers=w.headers).json()["study_tools"] for w in learners]
        assert seen == again  # stable per learner: no flicker between visits
        assert True in seen and False in seen  # a real cohort, not all or nothing
    finally:
        assert _set(client, op, "study_tools", 100).status_code == 200
    assert client.get("/v1/me/notes", headers=learner.headers).status_code == 200


def test_rollouts_are_operator_only_audited_and_snapshotted(client: TestClient) -> None:
    op = _operator(client)
    no_mfa = _operator(client, mfa=False)
    learner = _learner(client)
    assert _set(client, learner, "study_tools", 0).status_code == 403
    assert _set(client, no_mfa, "study_tools", 0).status_code == 403
    assert _set(client, op, "study_tools", 101).status_code == 422
    assert _set(client, op, "no_such_feature", 10).status_code == 404
    assert _set(client, op, "study_tools", 100, reason="short").status_code == 422
    assert _set(client, op, "study_tools", 100, reason="Fixture: confirm full rollout").status_code == 200
    snapshot = client.get(URL, headers=op.headers).json()
    row = next(r for r in snapshot["rollouts"] if r["key"] == "study_tools")
    assert row["percent"] == 100 and row["default_percent"] == 100 and snapshot["environment"]
    with get_sessionmaker()() as db:
        events = db.scalars(
            select(AuditEvent).where(AuditEvent.action == "ops.rollout_changed", AuditEvent.target_id == "study_tools")
        ).all()
    assert events


def test_the_release_manifest_records_rollout_defaults() -> None:
    from portal_api import release

    m = release.manifest()
    assert m["feature_rollouts"]["study_tools"]["production"] == 100
