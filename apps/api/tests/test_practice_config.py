"""P11.S3.T1 (PRACTICE-CONFIG-01): the practice builder's configuration, before a test starts.

* A chapter can be narrowed to its topics. Availability lists only topics that have questions, with their own counts,
  and a topic test draws only from that topic.
* The time estimate is measured, never guessed: the median time per question on submitted untimed practice in the
  class and subject. There is no estimate until ESTIMATE_MIN_TESTS tests exist, and implausible times (under 5 s or
  over 30 min a question) don't count.

Real PostgreSQL; technical fixture questions and labelled fixture tests only (removed afterwards).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from portal_api.modules.assessment import forms
from portal_api.modules.assessment.models import Attempt, PracticeForm
from portal_api.modules.curriculum.models import Topic
from tests.test_attempts import _learner, publish_physics_pool

CHAPTER_INDEX = 3  # this module's own pool; no other module uses it


def _availability(client: TestClient, who: Any) -> dict[str, Any]:
    r = client.get("/v1/practice/availability?grade=11&subject=physics", headers=who.headers)
    assert r.status_code == 200, r.text
    return dict(r.json())


def test_a_chapter_can_be_narrowed_to_its_topics(client: TestClient, db: Session) -> None:
    pool = publish_physics_pool(client, CHAPTER_INDEX)
    chapter = uuid.UUID(pool["chapter"])
    topic = db.scalar(select(Topic).where(Topic.chapter_id == chapter, Topic.retired_at.is_(None)))
    assert topic is not None
    tagged = pool["ids"][:2]  # a technical topic mapping for two of this module's fixture questions
    db.execute(text("update content_item set topic_id = :t where id = any(:i)"), {"t": topic.id, "i": tagged})
    db.commit()
    try:
        learner = _learner(client)
        entry = next(c for c in _availability(client, learner)["chapters"] if c["chapter_id"] == str(chapter))
        assert [(t["topic_id"], t["questions"]) for t in entry["topics"]] == [(str(topic.id), 2)]
        assert entry["topics"][0]["title"] == topic.title and entry["questions"] >= 2

        made = client.post(
            "/v1/practice/forms",
            headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex},
            json={
                "grade": 11,
                "subject": "physics",
                "chapter_ids": [str(chapter)],
                "topic_ids": [str(topic.id)],
                "question_count": 2,
            },
        )
        assert made.status_code == 201, made.text
        drawn = db.execute(
            text("select item_id::text from form_item where form_id = :f"), {"f": made.json()["id"]}
        ).scalars()
        assert set(drawn) == {str(i) for i in tagged}
        too_many = client.post(
            "/v1/practice/forms",
            headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex},
            json={
                "grade": 11,
                "subject": "physics",
                "chapter_ids": [str(chapter)],
                "topic_ids": [str(topic.id)],
                "question_count": 3,
            },
        )
        assert too_many.status_code == 422 and too_many.json()["available"] == 2  # said before anything starts
    finally:
        db.execute(text("update content_item set topic_id = null where id = any(:i)"), {"i": tagged})
        db.commit()


def _finished_tests(owner: uuid.UUID, subject: str, seconds_per_question: list[float]) -> None:
    """Labelled fixture tests: one untimed 10-question practice test per entry, submitted after that long a question."""
    now = datetime.now(UTC)
    with get_sessionmaker()() as s:
        for i, spq in enumerate(seconds_per_question):
            form = PracticeForm(
                owner_id=owner,
                idempotency_key=f"fixture-estimate-{uuid.uuid4().hex[:12]}",
                request_hash="0" * 64,
                kind="practice",
                grade_number=12,
                subject_code=subject,
                scope={},
                seed=i,
                question_count=10,
                duration_s=None,
                late_write_tolerance_ms=3000,
                feedback_mode="deferred",
            )
            s.add(form)
            s.flush()
            finished = now - timedelta(days=1, minutes=i)
            s.add(
                Attempt(
                    form_id=form.id,
                    user_id=owner,
                    status="finalised",
                    started_at=finished - timedelta(seconds=spq * 10),
                    tolerance_ms=3000,
                    finalised_at=finished,
                    finalise_reason="manual",
                )
            )
        s.commit()


def _remove(subject: str) -> None:
    with get_sessionmaker()() as s:
        ids = list(s.scalars(select(PracticeForm.id).where(PracticeForm.subject_code == subject)))
        s.execute(delete(Attempt).where(Attempt.form_id.in_(ids)))
        s.execute(delete(PracticeForm).where(PracticeForm.id.in_(ids)))
        s.commit()


def test_the_time_estimate_is_measured_or_absent(client: TestClient) -> None:
    learner = _learner(client)
    subject = f"fixture-estimate-{uuid.uuid4().hex[:8]}"  # isolated: nothing else is measured with it
    try:
        _finished_tests(learner.id, subject, [60.0] * (forms.ESTIMATE_MIN_TESTS - 1) + [2.0, 4000.0])
        with get_sessionmaker()() as s:
            assert forms.time_estimate(s, 12, subject) == (None, forms.ESTIMATE_MIN_TESTS - 1)  # too few real ones
        _finished_tests(learner.id, subject, [90.0, 90.0, 90.0])
        with get_sessionmaker()() as s:
            per_question, measured = forms.time_estimate(s, 12, subject)
        assert measured == forms.ESTIMATE_MIN_TESTS + 2 and per_question == 60  # the median, outliers left out
    finally:
        _remove(subject)

    out = _availability(client, learner)
    assert "seconds_per_question" in out and isinstance(out["estimate_based_on"], int)
    assert out["seconds_per_question"] is None or out["estimate_based_on"] >= forms.ESTIMATE_MIN_TESTS
