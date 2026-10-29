"""P09.S1.T3 (MULTI-SUBJECT-01): custom practice across several subjects of one class, with per-subject question
counts, an optional time limit and either feedback mode. It is labelled custom practice, never an official pattern.
Technical fixture questions only."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.test_attempts import _learner, _start, publish_physics_pool
from tests.test_mistake_notebook import _answer, _submit

URL = "/v1/practice/forms"


@pytest.fixture(scope="module")
def biology(client: TestClient) -> dict[str, Any]:
    # Biology 11: its rights are confirmed by other fixtures too. Chemistry 11 rights must stay unverified for
    # test_content_workflow, so Chemistry 11 only appears here with nothing published (the shortage case).
    return publish_physics_pool(client, index=10, subject="biology")


def _custom(client: TestClient, who: Any, mix: list[dict[str, Any]], **extra: Any) -> Any:
    body = {
        "grade": 11,
        "subject": mix[0]["subject"],
        "scope": "multi_subject",
        "mix": mix,
        "question_count": sum(m["questions"] for m in mix),
        **extra,
    }
    return client.post(URL, headers={**who.headers, "Idempotency-Key": uuid.uuid4().hex}, json=body)


def test_a_custom_test_mixes_subjects_with_their_own_counts(
    client: TestClient, physics: dict[str, Any], biology: dict[str, Any]
) -> None:
    learner = _learner(client)
    r = _custom(
        client,
        learner,
        [{"subject": "physics", "questions": 2}, {"subject": "biology", "questions": 3}],
        timed_minutes=15,
        feedback_mode="immediate",
    )
    assert r.status_code == 201, r.text
    form = r.json()
    assert form["question_count"] == 5 and form["duration_s"] == 15 * 60 and form["feedback_mode"] == "immediate"
    scope = form["scope"]
    assert scope["mode"] == "multi_subject" and "profile" not in scope  # custom practice, not an official pattern
    assert [(s["subject"], s["from"], s["to"]) for s in scope["sections"]] == [("physics", 1, 2), ("biology", 3, 5)]
    a = _start(client, learner, form["id"])
    subjects = [i["subject"] for i in a["items"]] if a["items"] and "subject" in a["items"][0] else None
    _answer(client, learner, form["id"], a, correct={1, 3})
    _submit(client, learner, a["id"])
    result = client.get(f"/v1/attempts/{a['id']}/result", headers=learner.headers).json()
    assert result["form"]["kind"] == "practice" and result["form"]["mode"] == "multi_subject"
    assert [s["label"].split(" · ")[0] for s in result["sections"]] == ["Physics", "Biology"]
    assert sum(s["maximum"] for s in result["sections"]) == result["maximum"]
    assert subjects is None or subjects == ["physics"] * 2 + ["biology"] * 3


def test_custom_mixes_are_validated_and_shortages_are_honest(
    client: TestClient, physics: dict[str, Any], biology: dict[str, Any]
) -> None:
    learner = _learner(client)
    one = _custom(client, learner, [{"subject": "physics", "questions": 2}])
    assert one.status_code == 422  # one subject is an ordinary practice test
    twice = _custom(client, learner, [{"subject": "physics", "questions": 1}, {"subject": "physics", "questions": 1}])
    assert twice.status_code == 422
    inactive = _custom(client, learner, [{"subject": "physics", "questions": 1}, {"subject": "urdu", "questions": 1}])
    assert inactive.status_code == 422
    mismatch = _custom(
        client,
        learner,
        [{"subject": "physics", "questions": 1}, {"subject": "biology", "questions": 1}],
        question_count=3,
    )
    assert mismatch.status_code == 422
    short = _custom(
        client, learner, [{"subject": "physics", "questions": 2}, {"subject": "chemistry", "questions": 90}]
    )
    assert short.status_code == 422 and short.json()["code_reason"] == "POOL_SHORTAGE", short.text
    (gap,) = short.json()["sections"]
    assert gap["subject"] == "chemistry" and gap["required"] == 90
