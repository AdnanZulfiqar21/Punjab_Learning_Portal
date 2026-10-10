"""P09.S4.T3 (FORM-REPLACE-01), §5.7 before start: a question quarantined after an unstarted test was built is
replaced from the same approved pool (same chapters, or the same mock section) when a replacement exists, so the
learner can still start; with no replacement the test is withdrawn honestly. Started tests are never touched.
Technical fixture questions only."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from tests.test_attempts import POOL, _form, _form_item_ids, _learner, _start
from tests.test_content_workflow import Staff, _post
from tests.test_mocks import _publish_profile


def _families(form_id: str) -> dict[int, str]:
    with get_sessionmaker()() as db:
        rows = db.execute(text("select position, family_id from form_item where form_id = :f"), {"f": form_id}).all()
        return {int(p): str(f) for p, f in rows}


def _scope(form_id: str) -> dict[str, Any]:
    with get_sessionmaker()() as db:
        return dict(db.execute(text("select scope from practice_form where id = :f"), {"f": form_id}).scalar_one())


def test_a_quarantined_question_is_replaced_before_start(client: TestClient, physics: dict[str, Any]) -> None:
    learner = _learner(client)
    form = _form(client, learner, physics["chapter"], count=2).json()
    before = _form_item_ids(form["id"])
    item = before[2]
    pub = physics["publisher"]
    try:
        assert (
            _post(client, pub, item, "quarantine", {"reason": "Fixture: suspected", "level": "SOFT"}).status_code == 200
        )
        attempt = _start(client, learner, form["id"])  # starts: the question was replaced, not refused
        after = _form_item_ids(form["id"])
        assert after[1] == before[1] and after[2] != item and item not in after.values()
        assert len(set(_families(form["id"]).values())) == 2  # still one question per family
        (log,) = _scope(form["id"])["replaced"]
        assert log["position"] == 2 and log["reason"] == "superseded"
        view = client.get(f"/v1/attempts/{attempt['id']}", headers=learner.headers)
        assert view.status_code == 200 and len(view.json()["items"]) == 2

        started = _form(client, learner, physics["chapter"], count=2).json()  # a started test is never changed
        frozen = _form_item_ids(started["id"])
        _start(client, learner, started["id"])
    finally:
        _post(client, pub, item, "release", {"reason": "Fixture: not a defect"})
    assert _form_item_ids(started["id"]) == frozen


def test_a_mock_replacement_stays_in_its_section(client: TestClient, db: Session, physics: dict[str, Any]) -> None:
    code = _publish_profile(client, db, [{"subject": "physics", "grades": [11], "questions": 2}])
    learner = _learner(client)
    mock = client.post(
        "/v1/mocks", headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex}, json={"code": code}
    ).json()
    item = _form_item_ids(mock["id"])[1]
    pub = physics["publisher"]
    try:
        assert (
            _post(client, pub, item, "quarantine", {"reason": "Fixture: suspected", "level": "SOFT"}).status_code == 200
        )
        _start(client, learner, mock["id"])
        after = _form_item_ids(mock["id"])
        assert item not in after.values() and len(after) == 2
        assert _scope(mock["id"])["sections"][0]["to"] == 2  # the blueprint is unchanged
    finally:
        _post(client, pub, item, "release", {"reason": "Fixture: not a defect"})


def test_without_a_replacement_the_test_is_withdrawn(client: TestClient, physics: dict[str, Any]) -> None:
    learner = _learner(client)
    form = _form(client, learner, physics["chapter"], count=POOL).json()  # uses every question: nothing to swap in
    item = _form_item_ids(form["id"])[1]
    pub = physics["publisher"]
    try:
        assert (
            _post(client, pub, item, "quarantine", {"reason": "Fixture: suspected", "level": "SOFT"}).status_code == 200
        )
        r = client.post(f"/v1/practice/forms/{form['id']}/attempt", headers=learner.headers)
        assert r.status_code == 409 and r.json()["code_reason"] == "FORM_SUPERSEDED"
        assert _form_item_ids(form["id"])[1] == item  # nothing half-replaced
    finally:
        _post(client, pub, item, "release", {"reason": "Fixture: not a defect"})


def _stream(client: TestClient, who: Any, stream: str) -> None:
    r = client.put("/v1/me/profile", headers=who.headers, json={"stream": stream})
    assert r.status_code == 200, r.text


def test_patterns_are_shown_for_the_learners_stream_and_say_whether_they_can_start(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    sections = [{"subject": "physics", "grades": [11], "questions": 2}]
    engineering = _publish_profile(client, db, sections, streams=["pre_engineering"])
    everyone = _publish_profile(client, db, sections)
    learner = _learner(client)

    def codes() -> set[str]:
        r = client.get("/v1/exam-profiles", headers=learner.headers)
        assert r.status_code == 200, r.text
        return {p["code"] for p in r.json()}

    assert {engineering, everyone} <= codes()  # no stream on the profile yet: nothing is hidden
    _stream(client, learner, "pre_medical")
    assert everyone in codes() and engineering not in codes()
    _stream(client, learner, "pre_engineering")
    assert {engineering, everyone} <= codes()

    ready = client.get(f"/v1/mocks/{everyone}/readiness", headers=learner.headers).json()
    assert ready["ready"] is True and ready["entitled"] is True
    with get_sessionmaker()() as s:
        none = Staff(client, s, [])  # no trial or plan
    blocked = client.get(f"/v1/mocks/{everyone}/readiness", headers=none.headers).json()
    assert blocked["ready"] is True and blocked["entitled"] is False  # stocked, but this learner needs a plan
