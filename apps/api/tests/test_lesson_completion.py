"""P07.S1.T3 / §6.6 (LESSON-DONE-01): learners mark readable lessons complete; the content-completed meter uses it."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests import test_content_workflow
from tests.test_attempts import _learner
from tests.test_content_workflow import Staff, _confirm_rights, _post, _submitted

team = test_content_workflow.team


def _meter(client: TestClient, who: Staff) -> Any:
    r = client.get("/v1/me/evidence", headers=who.headers, params={"grade": 11, "subject": "biology"})
    return r.json()["meters"]["content_completed"]["value"]


def test_completion_is_for_readable_live_lessons_and_feeds_the_meter(
    client: TestClient, db: Session, team: dict[str, Staff]
) -> None:
    item, chapter, doc = _submitted(client, db, team)
    _confirm_rights(client, db, doc)
    assert (
        _post(
            client, team["reviewer"], item["id"], "review", {"decision": "approve", "comment": "Fixture check"}
        ).status_code
        == 200
    )
    assert _post(client, team["publisher"], item["id"], "publish").status_code == 200
    url = f"/v1/me/lessons/{item['id']}/complete"
    no_plan = Staff(client, db, [])
    assert client.post(url, headers=no_plan.headers).status_code == 403  # premium lesson, no trial
    learner = _learner(client)
    before = _meter(client, learner)
    assert client.post(url, headers=learner.headers).status_code == 204
    assert client.post(url, headers=learner.headers).status_code == 204  # idempotent
    done = client.get(f"/v1/me/chapters/{chapter.id}/completed-lessons", headers=learner.headers).json()
    assert done == [item["id"]]
    after = _meter(client, learner)
    assert after is not None and (before or 0) < after
    assert client.delete(url, headers=learner.headers).status_code == 204
    assert client.get(f"/v1/me/chapters/{chapter.id}/completed-lessons", headers=learner.headers).json() == []
    draft = _submitted(client, db, team)[0]
    assert client.post(f"/v1/me/lessons/{draft['id']}/complete", headers=learner.headers).status_code == 404
