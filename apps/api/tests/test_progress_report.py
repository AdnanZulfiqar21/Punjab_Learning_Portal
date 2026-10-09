"""P12.S4.T2 (PROGRESS-01): the progress report reflects latest score versions with stated definitions."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests import test_attempts
from tests.test_attempts import POOL, _form, _learner, _start
from tests.test_mistake_notebook import _answer

physics = test_attempts.physics


def test_progress_counts_answered_and_correct_questions(client: TestClient, physics: dict[str, Any]) -> None:
    learner = _learner(client)
    empty = client.get("/v1/me/progress", headers=learner.headers).json()
    assert empty["subjects"] == [] and set(empty["definitions"]) >= {"accuracy", "score", "questions_answered"}
    form = _form(client, learner, physics["chapter"], count=POOL).json()
    attempt = _start(client, learner, form["id"])
    _answer(client, learner, form["id"], attempt, correct={1, 2})
    r = client.post(
        f"/v1/attempts/{attempt['id']}/submit",
        headers=learner.headers,
        json={"idempotency_key": uuid.uuid4().hex, "ops": []},
    )
    assert r.status_code == 200
    report = client.get("/v1/me/progress", headers=learner.headers).json()
    physics_row = next(s for s in report["subjects"] if s["subject"] == "physics" and s["grade"] == 11)
    assert physics_row["tests"] == 1 and physics_row["questions_answered"] == POOL and physics_row["correct"] == 2
    assert physics_row["accuracy"] == round(100 * 2 / POOL, 1)
    assert report["recent"][0]["attempt_id"] == attempt["id"] and report["recent"][0]["score_version"] == 1
    assert report["notebook"]["open"] == POOL - 2
    assert client.get("/v1/me/progress").status_code == 401
