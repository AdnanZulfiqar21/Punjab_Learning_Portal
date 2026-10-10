"""P16.S2.T1 (ANALYTICS-EVENTS-01): the event dictionary is the only way to record an event; events carry no private
data or answer content; retries and replays are recorded once. Technical fixture questions and lessons only."""

from __future__ import annotations

import uuid
from collections import Counter
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from portal_api.modules.analytics import events
from portal_api.modules.analytics.events import AnalyticsEvent
from tests import test_content_workflow
from tests.test_attempts import POOL, _form, _learner, _op, _save_ops, _start
from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _create, _post, _refs, _save
from tests.test_mistake_notebook import _submit

team = test_content_workflow.team


def _events(user_id: Any) -> list[AnalyticsEvent]:
    with get_sessionmaker()() as db:
        return list(db.scalars(select(AnalyticsEvent).where(AnalyticsEvent.user_id == user_id)))


def test_the_dictionary_never_names_private_data() -> None:
    for name, spec in events.DICTIONARY.items():
        for prop in spec.props:
            assert not set(prop.split("_")) & set(events.FORBIDDEN), (name, prop)  # whole words, e.g. not `option_id`
        assert spec.emitted or spec.note, name  # a defined-but-silent event says why


@pytest.mark.parametrize(
    ("name", "props", "why"),
    [
        ("nope", {}, "unknown event"),
        ("purchase.completed", {"product_code": "x"}, "not emitted"),
        ("trial.decided", {"state": "granted"}, "missing"),
        ("trial.decided", {"state": "granted", "surface": "web", "email": "a@b"}, "unknown"),
        (
            "answer.saved",
            {"attempt_id": "a", "position": "1", "state": "accepted", "cleared": False, "via": "save"},
            "int",
        ),
        (
            "answer.saved",
            {"attempt_id": "a", "position": 1, "state": "maybe", "cleared": False, "via": "save"},
            "one of",
        ),
    ],
)
def test_anything_outside_the_dictionary_is_refused(name: str, props: dict[str, Any], why: str) -> None:
    with pytest.raises(events.EventRejected, match=why):
        events.validate(name, props)


def test_a_practice_journey_records_each_event_once_without_answers(
    client: TestClient, physics: dict[str, Any]
) -> None:
    learner = _learner(client)
    form = _form(client, learner, physics["chapter"], count=POOL).json()
    attempt = _start(client, learner, form["id"])
    assert _start(client, learner, form["id"])["id"] == attempt["id"]  # idempotent start: one event
    first = attempt["items"][0]
    op = _op(first["position"], 1, first["options"][0]["id"])
    assert _save_ops(client, learner, attempt["id"], op).status_code == 200
    assert _save_ops(client, learner, attempt["id"], op).status_code == 200  # an exact replay: no second event
    _submit(client, learner, attempt["id"])
    rows = _events(learner.id)
    counts = Counter(e.name for e in rows)
    assert counts["attempt.started"] == 1 and counts["answer.saved"] == 1
    assert counts["attempt.submitted"] == 1 and counts["score.version_created"] == 1
    assert counts["trial.decided"] == 1  # the trial the fixture learner started
    option_ids = {o["id"] for item in attempt["items"] for o in item["options"]}
    for e in rows:
        assert set(e.properties) == set(events.DICTIONARY[e.name].props)
        assert not option_ids & {str(v) for v in e.properties.values()}  # never the chosen option
    saved = next(e for e in rows if e.name == "answer.saved")
    assert saved.properties["state"] == "accepted" and saved.properties["cleared"] is False


def test_lesson_started_is_daily_and_needs_a_published_lesson(
    client: TestClient, db: Session, team: dict[str, Staff]
) -> None:
    chapter, doc = _chapter(db, 11, "biology", 8)
    _confirm_rights(client, db, doc)
    lesson = _create(client, team["author"], chapter)
    assert _save(client, team["author"], lesson, refs=_refs(chapter, doc)).status_code == 200
    assert _post(client, team["author"], lesson["id"], "submit", {"note": "ready"}).status_code == 200
    review = {"decision": "approve", "comment": "Fixture check"}
    assert _post(client, team["reviewer"], lesson["id"], "review", review).status_code == 200
    assert _post(client, team["publisher"], lesson["id"], "publish").status_code == 200
    learner = Staff(client, db, [])
    url = "/v1/me/events/lesson-started"
    assert client.post(url, headers=learner.headers, json={"lesson_id": str(uuid.uuid4())}).status_code == 404
    for _ in range(2):
        assert client.post(url, headers=learner.headers, json={"lesson_id": lesson["id"]}).status_code == 204
    assert Counter(e.name for e in _events(learner.id))["lesson.started"] == 1


def test_the_dictionary_is_readable_by_its_owners_only(client: TestClient, db: Session) -> None:
    url = "/v1/admin/analytics/dictionary"
    assert client.get(url, headers=Staff(client, db, [], mfa=True).headers).status_code == 403
    doc = client.get(url, headers=Staff(client, db, ["owner_admin"], mfa=True).headers).json()
    names = {d["name"]: d for d in doc}
    assert names["purchase.completed"]["emitted"] is False and "B06" in names["purchase.completed"]["note"]
    assert names["checkpoint.answered"]["emitted"] is False
