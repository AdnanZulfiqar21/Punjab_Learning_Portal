"""P12.S1.T1 (RESULT-SUMMARY-01): a result says how long the test took, which pattern and version it followed, how each
section went, how its score has changed over time and how many questions were excluded, credited or unanswered.
Technical fixture questions and profiles only."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_attempts import POOL, _form, _learner, _start
from tests.test_mistake_notebook import _answer, _submit
from tests.test_mocks import _publish_profile


def test_practice_and_mock_results_carry_the_full_summary(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    learner = _learner(client)
    form = _form(client, learner, physics["chapter"], count=POOL).json()
    attempt = _start(client, learner, form["id"])
    _answer(client, learner, form["id"], attempt, correct={1, 2})
    _submit(client, learner, attempt["id"])
    r = client.get(f"/v1/attempts/{attempt['id']}/result", headers=learner.headers).json()
    t = r["timing"]
    assert t["started_at"] and t["finalised_at"] and t["seconds_used"] >= 0 and t["time_limit_s"] is None
    assert r["form"]["kind"] == "practice" and r["form"]["profile"] is None
    assert r["sections"] == []  # practice tests have no sections
    assert [h["version"] for h in r["history"]] == [1] and r["history"][0]["reason"]
    assert r["counts"] == {"excluded": 0, "credited": 0, "unanswered": 0, "not_scorable": False}

    code = _publish_profile(client, db, [{"subject": "physics", "grades": [11], "questions": 2}])
    mock = client.post(
        "/v1/mocks", headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex}, json={"code": code}
    )
    assert mock.status_code == 201, mock.text
    ma = _start(client, learner, mock.json()["id"])
    _answer(client, learner, mock.json()["id"], ma, correct={1})
    _submit(client, learner, ma["id"])
    m = client.get(f"/v1/attempts/{ma['id']}/result", headers=learner.headers).json()
    assert m["form"]["kind"] == "mock" and m["form"]["profile"] == code and m["form"]["profile_version"] == 1
    assert m["timing"]["time_limit_s"] == 30 * 60
    (section,) = m["sections"]
    assert (section["from_position"], section["to_position"]) == (1, 2) and "Physics" in section["label"]
    assert (section["raw"], section["maximum"]) == (m["raw"], m["maximum"])  # one section: the whole test
