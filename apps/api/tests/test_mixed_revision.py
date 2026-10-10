"""P12.S3.T3 (MIXED-REVISION-01): a review test mixes in a controlled share of already-mastered questions (interleaved
retrieval), never more than MIXED_SHARE of the test and only alongside due work. Getting one wrong reopens it.
Technical fixture questions only; entry states are set with SQL purely as test setup."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from portal_api.modules.assessment import notebook
from tests.test_attempts import POOL, _form, _learner, _start
from tests.test_mistake_notebook import _answer, _make_due, _submit

URL = "/v1/me/notebook/review"


def test_reviews_mix_in_a_bounded_share_of_mastered_questions(client: TestClient, physics: dict[str, Any]) -> None:
    learner = _learner(client)
    form = _form(client, learner, physics["chapter"], count=POOL).json()
    attempt = _start(client, learner, form["id"])
    _answer(client, learner, form["id"], attempt, correct=set())
    _submit(client, learner, attempt["id"])
    _make_due(learner.id)
    with get_sessionmaker()() as db:
        ids = [str(i) for i in db.execute(
            text("select id from mistake_entry where user_id = :u order by id"), {"u": str(learner.id)}
        ).scalars()]  # fmt: skip
        mastered = ids[:3]
        db.execute(text("update mistake_entry set status = 'mastered' where id = any(:m)"), {"m": mastered})
        db.commit()
    body = {"grade": 11, "subject": "physics", "count": 10}
    review = client.post(URL, headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex}, json=body)
    assert review.status_code == 201, review.text
    scope = review.json()["scope"]
    mixed = scope["mixed"]
    assert len(mixed) == int(10 * notebook.MIXED_SHARE) and set(mixed) <= set(mastered)  # bounded share
    assert set(scope["entries"]) - set(mixed) == set(ids[3:])  # every due entry is still there
    assert review.json()["question_count"] == 3 + len(mixed)

    with get_sessionmaker()() as db:  # nothing due: mastered material alone never makes a review
        db.execute(text("update mistake_entry set status = 'mastered' where user_id = :u"), {"u": str(learner.id)})
        db.commit()
    none = client.post(URL, headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex}, json=body)
    assert none.status_code == 422 and none.json()["code_reason"] == "NOTHING_DUE"
