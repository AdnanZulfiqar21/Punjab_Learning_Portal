"""OCT9-03: progress buckets use each frozen question's class and subject, not the form's label. A mixed mock or a
combined XI+XII test counts in every bucket it touches, with its overall result kept separately.
Fixture questions only."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from tests.test_attempts import POOL, _learner, _start
from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _post, _refs
from tests.test_mcq_items import CHECKS, VALID, _new_mcq, _save
from tests.test_mistake_notebook import _answer, _submit
from tests.test_mocks import _publish_profile


def _publish(client: TestClient, grade: int, subject: str, n: int) -> None:
    with get_sessionmaker()() as db:
        scope = {"grades": [grade], "subjects": [subject]}
        author = Staff(client, db, ["content_author"], scope)
        reviewer = Staff(client, db, ["subject_reviewer"], scope)
        publisher = Staff(client, db, ["publisher"], scope, mfa=True)
        chapter, doc = _chapter(db, grade, subject)
        _confirm_rights(client, db, doc)
    for i in range(n):
        item = _new_mcq(client, author, str(chapter.id))
        body = copy.deepcopy(VALID)
        body["explanation"]["distractors"] = {}
        body["stem"] = [{"type": "paragraph", "text": f"Fixture {subject} {grade} stem {i}"}]
        assert _save(client, author, item, body, _refs(chapter, doc)).status_code == 200
        assert _post(client, author, item["id"], "submit").status_code == 200
        review = {"decision": "approve", "comment": "Fixture check", "checklist": CHECKS}
        assert _post(client, reviewer, item["id"], "review", review).status_code == 200
        assert _post(client, publisher, item["id"], "publish").status_code == 200


def _form_of(attempt_id: str) -> str:
    with get_sessionmaker()() as db:
        return str(db.execute(text("select form_id from attempt where id = :a"), {"a": attempt_id}).scalar_one())


def test_a_mixed_mock_counts_in_each_class_and_subject(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    _publish(client, 12, "chemistry", 2)
    code = _publish_profile(
        client,
        db,
        [
            {"subject": "physics", "grades": [11], "questions": 2},
            {"subject": "chemistry", "grades": [12], "questions": 2},
        ],
    )
    learner = _learner(client)
    form = client.post(
        "/v1/mocks", headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex}, json={"code": code}
    )
    assert form.status_code == 201, form.text
    attempt = _start(client, learner, form.json()["id"])
    _answer(client, learner, form.json()["id"], attempt, correct={1, 2})  # both physics right, both chemistry wrong
    _submit(client, learner, attempt["id"])
    report = client.get("/v1/me/progress", headers=learner.headers).json()
    buckets = {(s["grade"], s["subject"]): s for s in report["subjects"]}
    assert set(buckets) == {(11, "physics"), (12, "chemistry")}
    assert (buckets[(11, "physics")]["questions_answered"], buckets[(11, "physics")]["correct"]) == (2, 2)
    assert (buckets[(12, "chemistry")]["questions_answered"], buckets[(12, "chemistry")]["correct"]) == (2, 0)
    assert all(b["tests"] == 1 for b in buckets.values())  # a mixed test counts in each bucket it touches
    (recent,) = report["recent"]
    assert (recent["raw"], recent["maximum"]) == (2, 8)  # whole result: 2 right x 2 marks, 2 wrong x -1
    assert sorted((p["grade"], p["subject"]) for p in recent["parts"]) == [(11, "physics"), (12, "chemistry")]


def test_a_combined_test_reports_each_class(client: TestClient, physics: dict[str, Any]) -> None:
    _publish(client, 12, "physics", 2)
    learner = _learner(client)
    for _ in range(20):  # sampling is random: use the first combined test that includes Class XII questions
        form = client.post(
            "/v1/practice/forms",
            headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex},
            json={"grade": 11, "subject": "physics", "question_count": POOL, "scope": "combined"},
        )
        assert form.status_code == 201, form.text
        with get_sessionmaker()() as db:
            per_grade = dict(
                db.execute(
                    text(
                        "select ci.grade_number, count(*) from form_item fi join content_item ci on ci.id = fi.item_id "
                        "where fi.form_id = :f group by ci.grade_number"
                    ),
                    {"f": form.json()["id"]},
                ).all()
            )
        if 12 in per_grade:
            break
    assert 12 in per_grade
    attempt = _start(client, learner, form.json()["id"])
    _answer(client, learner, form.json()["id"], attempt, correct=set())
    _submit(client, learner, attempt["id"])
    report = client.get("/v1/me/progress", headers=learner.headers).json()
    buckets = {(s["grade"], s["subject"]): s for s in report["subjects"]}
    assert {g: b["questions_answered"] for (g, _), b in buckets.items()} == per_grade
