"""P10.S3.T3 (RECOVERABLE-SCORING-01): a scoring failure never fails a submission. The attempt is finalised with its
receipt, the result says "submitted, scoring pending", and a retry pass scores it exactly once (one score version, one
score event). Technical fixture questions only."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from portal_api.db import get_sessionmaker
from portal_api.modules.analytics.events import AnalyticsEvent
from portal_api.modules.assessment import attempts, scoring
from portal_api.modules.assessment.models import Attempt, ScoreVersion
from tests.test_attempts import POOL, _form, _learner, _start
from tests.test_mistake_notebook import _answer


def test_a_scoring_failure_leaves_a_durable_submission_that_is_scored_later(
    client: TestClient, physics: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    learner = _learner(client)
    form = _form(client, learner, physics["chapter"], count=POOL).json()
    attempt = _start(client, learner, form["id"])
    _answer(client, learner, form["id"], attempt, correct={1})

    def broken(*_: Any, **__: Any) -> Any:
        raise RuntimeError("Fixture: scoring unavailable")

    monkeypatch.setattr(scoring, "score", broken)
    sub = client.post(
        f"/v1/attempts/{attempt['id']}/submit",
        headers=learner.headers,
        json={"idempotency_key": uuid.uuid4().hex, "ops": []},
    )
    assert sub.status_code == 200, sub.text  # the learner's submission succeeded
    pending = client.get(f"/v1/attempts/{attempt['id']}/result", headers=learner.headers)
    assert pending.status_code == 409 and pending.json()["code_reason"] == "SCORING_PENDING"
    assert client.get(f"/v1/attempts/{attempt['id']}", headers=learner.headers).json()["status"] == "finalised"
    monkeypatch.undo()

    with get_sessionmaker()() as db:
        assert attempts.score_pending(db) >= 1
        assert attempts.score_pending(db) == 0  # nothing left: a second pass changes nothing
    ok = client.get(f"/v1/attempts/{attempt['id']}/result", headers=learner.headers)
    assert ok.status_code == 200 and ok.json()["version"] == 1
    with get_sessionmaker()() as db:
        aid = uuid.UUID(attempt["id"])
        assert db.scalar(select(func.count()).select_from(ScoreVersion).where(ScoreVersion.attempt_id == aid)) == 1
        events = db.scalar(
            select(func.count())
            .select_from(AnalyticsEvent)
            .where(
                AnalyticsEvent.name == "score.version_created",
                AnalyticsEvent.properties["attempt_id"].astext == attempt["id"],
            )
        )
        assert events == 1
        a = db.get(Attempt, aid)
        assert a is not None and a.notebook_applied_at is not None  # the notebook caught up too
