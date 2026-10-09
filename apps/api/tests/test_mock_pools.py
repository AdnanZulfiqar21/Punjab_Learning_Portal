"""P08.S3.T3 (MOCKPOOL-01): mock-reserved questions never reach practice tests; mocks draw from them and prefer
questions the learner hasn't seen. Questions are technical fixtures."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from tests import test_attempts
from tests.test_attempts import _learner, _post
from tests.test_mocks import _mock, _publish_profile

physics = test_attempts.physics


def _practice_count(client: TestClient, who: Any, chapter: str) -> int:
    av = client.get("/v1/practice/availability?grade=11&subject=physics", headers=who.headers).json()
    return int(next(c for c in av["chapters"] if c["chapter_id"] == chapter)["questions"])


def test_mock_pool_is_kept_out_of_practice_and_exposure_is_spread(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    pub, learner = physics["publisher"], _learner(client)
    reserved = physics["ids"][:4]
    before = _practice_count(client, learner, physics["chapter"])
    author = physics["author"]
    assert _post(client, author, reserved[0], "question-pool", {"pool": "mock", "reason": "Fixture"}).status_code == 403
    try:
        for item in reserved:
            r = _post(client, pub, item, "question-pool", {"pool": "mock", "reason": "Fixture: mock-only"})
            assert r.status_code == 200 and r.json()["question_pool"] == "mock", r.text
        after = _practice_count(client, learner, physics["chapter"])
        assert after == before - 4
        form = client.post(
            "/v1/practice/forms",
            headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex},
            json={"grade": 11, "subject": "physics", "chapter_ids": [physics["chapter"]], "question_count": after},
        ).json()
        with get_sessionmaker()() as s:
            used = {
                str(i)
                for i in s.execute(
                    text("select item_id from form_item where form_id = :f"), {"f": form["id"]}
                ).scalars()
            }
        assert not used & set(reserved)  # practice never meets a mock-reserved question
        code = _publish_profile(
            client, db, [{"subject": "physics", "grades": [11], "questions": 2}], question_pool="mock"
        )
        first = _mock(client, learner, code).json()
        second = _mock(client, learner, code).json()
        third = _mock(client, learner, code).json()
        assert [f["scope"]["sections"][0]["reused"] for f in (first, second, third)] == [0, 0, 2]
        assert first["scope"]["question_pool"] == "mock"
    finally:
        for item in reserved:
            _post(client, pub, item, "question-pool", {"pool": "practice", "reason": "Fixture cleanup"})
