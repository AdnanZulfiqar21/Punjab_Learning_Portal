"""Review tests are practice: they never use mock-reserved questions (MOCKPOOL-01's promise), and a reused request key
with a different request is refused instead of silently returning the earlier test. Technical fixture questions only."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.test_attempts import POOL, _form, _learner, _start
from tests.test_mistake_notebook import _answer, _make_due, _submit
from tests.test_mock_pools import _post

URL = "/v1/me/notebook/review"


def _missed_everything(client: TestClient, physics: dict[str, Any]) -> Any:
    learner = _learner(client)
    form = _form(client, learner, physics["chapter"], count=POOL).json()
    attempt = _start(client, learner, form["id"])
    _answer(client, learner, form["id"], attempt, correct=set())
    _submit(client, learner, attempt["id"])
    _make_due(learner.id)
    return learner


def test_a_review_never_uses_a_mock_reserved_question(client: TestClient, physics: dict[str, Any]) -> None:
    learner = _missed_everything(client, physics)
    pub, reserved = physics["publisher"], physics["ids"]
    try:
        for item in reserved:
            r = _post(client, pub, item, "question-pool", {"pool": "mock", "reason": "Fixture: mock-only"})
            assert r.status_code == 200, r.text
        body = {"grade": 11, "subject": "physics", "count": POOL}
        rv = client.post(URL, headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex}, json=body)
        assert rv.status_code == 422 and rv.json()["code_reason"] == "NOTHING_DUE", rv.text
    finally:
        for item in reserved:
            _post(client, pub, item, "question-pool", {"pool": "practice", "reason": "Fixture cleanup"})


def test_a_reused_key_with_a_different_request_is_refused(client: TestClient, physics: dict[str, Any]) -> None:
    learner = _missed_everything(client, physics)
    key = uuid.uuid4().hex
    first = client.post(
        URL, headers={**learner.headers, "Idempotency-Key": key}, json={"grade": 11, "subject": "physics", "count": 2}
    )
    assert first.status_code == 201, first.text
    same = client.post(
        URL, headers={**learner.headers, "Idempotency-Key": key}, json={"grade": 11, "subject": "physics", "count": 2}
    )
    assert same.status_code == 201 and same.json()["id"] == first.json()["id"]
    other = client.post(
        URL, headers={**learner.headers, "Idempotency-Key": key}, json={"grade": 11, "subject": "physics", "count": 3}
    )
    assert other.status_code == 409, other.text
