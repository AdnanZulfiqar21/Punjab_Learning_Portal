"""P16.S2.T3 (LEARNING-REPORT-01): outcomes beside engagement for one book, never blended; learners without answers are
not assessed (not zero); coverage and watch time unavailable with blockers; causation framed as a hypothesis.
Fixture questions; the learner's issuer is changed to a non-development one purely as test setup."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from portal_api.modules.analytics.learning import _bucket
from tests.test_attempts import POOL, _form, _learner, _start
from tests.test_content_workflow import Staff
from tests.test_mistake_notebook import _answer, _submit


def test_buckets_cover_every_share() -> None:
    assert _bucket(0) == (0, 0) and _bucket(0.4) == (0, 25) and _bucket(25) == (0, 25)
    assert _bucket(25.1) == (25, 50) and _bucket(100) == (75, 100)


def test_outcomes_and_engagement_side_by_side(client: TestClient, db: Session, physics: dict[str, Any]) -> None:
    viewer = Staff(client, db, ["finance"], mfa=True)
    url = "/v1/admin/analytics/learning"
    q = {"grade": 11, "subject": "physics"}
    assert client.get(url, headers=Staff(client, db, [], mfa=True).headers, params=q).status_code == 403
    before = client.get(url, headers=viewer.headers, params=q).json()
    learner = _learner(client)
    form = _form(client, learner, physics["chapter"], count=POOL).json()
    attempt = _start(client, learner, form["id"])
    _answer(client, learner, form["id"], attempt, correct=set(range(1, POOL + 1)))
    _submit(client, learner, attempt["id"])
    _learner(client)  # a test account with no answers: never assessed, never counted
    with get_sessionmaker()() as s:
        s.execute(
            text("update app_user set issuer = 'https://idp.fixture.invalid/' where id = :u"), {"u": str(learner.id)}
        )
        s.commit()
    r = client.get(url, headers=viewer.headers, params=q)
    assert r.status_code == 200, r.text
    after = r.json()
    o = after["outcomes"]
    assert o["learners_assessed"] - before["outcomes"]["learners_assessed"] == 1
    assert sum(b["learners"] for b in o["distribution"]) == o["learners_assessed"]
    assert o["rules_version"] == "evidence_rules_v2" and o["sample_limit"] >= 1 and o["topics_in_book"] > 0
    assert set(after["engagement"]) == {
        "live_lessons",
        "learners_completing",
        "median_completed_pct",
        "lesson_visit_days_30d",
    }
    assert after["unavailable"] == {"syllabus_coverage": "B02", "watch_time": "B05"}
    assert "hypothesis" in after["note"]
    assert client.get(url, headers=viewer.headers, params={"grade": 11, "subject": "astronomy"}).status_code == 404
