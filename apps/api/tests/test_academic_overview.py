"""P16.S1.T2 (ACADEMIC-OVERVIEW-01): per-chapter coverage, pipeline, quarantines, reports and pool sufficiency."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from portal_api.db import get_sessionmaker
from tests import test_attempts
from tests.test_attempts import _post
from tests.test_content_workflow import Staff

physics = test_attempts.physics


def test_overview_counts_live_families_and_quarantines(client: TestClient, physics: dict[str, Any]) -> None:
    pub = physics["publisher"]
    r = client.get("/v1/studio/overview", headers=pub.headers, params={"grade": 11, "subject": "physics"})
    assert r.status_code == 200, r.text
    body = r.json()
    row = next(c for c in body["chapters"] if c["chapter_id"] == physics["chapter"])
    assert row["live_mcq_families"] >= test_attempts.POOL and row["pool_sufficient"] is True
    before = row["live_mcq_families"]
    item = physics["ids"][0]
    try:
        assert (
            _post(client, pub, item, "quarantine", {"reason": "Fixture overview", "level": "SOFT"}).status_code == 200
        )
        after = client.get(
            "/v1/studio/overview", headers=pub.headers, params={"grade": 11, "subject": "physics"}
        ).json()
        row2 = next(c for c in after["chapters"] if c["chapter_id"] == physics["chapter"])
        assert row2["live_mcq_families"] == before - 1 and row2["quarantined"] >= 1
        assert after["totals"]["quarantined"] >= 1
    finally:
        _post(client, pub, item, "release", {"reason": "Fixture overview done"})
    with get_sessionmaker()() as db:
        learner = Staff(client, db, [])
        other_scope = Staff(client, db, ["publisher"], {"grades": [12], "subjects": ["physics"]}, mfa=True)
    q = {"grade": 11, "subject": "physics"}
    assert client.get("/v1/studio/overview", headers=learner.headers, params=q).status_code == 403
    assert client.get("/v1/studio/overview", headers=other_scope.headers, params=q).status_code == 403
