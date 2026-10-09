"""P12.S3 (NOTEBOOK-01): wrong answers fill the notebook; review tests follow 1/3/7/14-day spacing; a voided question
stays in the notebook with its reason. Technical fixture questions only."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from tests.test_attempts import POOL, _form, _form_item_ids, _learner, _op, _post, _save_ops, _start
from tests.test_content_workflow import Staff
from tests.test_mcq_corrections import _keys


def _submit(client: TestClient, who: Any, attempt_id: str) -> None:
    r = client.post(
        f"/v1/attempts/{attempt_id}/submit", headers=who.headers, json={"idempotency_key": uuid.uuid4().hex, "ops": []}
    )
    assert r.status_code == 200, r.text


def _answer(client: TestClient, who: Any, form_id: str, attempt: dict[str, Any], correct: set[int]) -> None:
    keys = _keys(form_id)
    ops = []
    for item in attempt["items"]:
        p = item["position"]
        wrong = next(o["id"] for o in item["options"] if o["id"] != keys[p])
        ops.append(_op(p, 1, keys[p] if p in correct else wrong))
    assert _save_ops(client, who, attempt["id"], *ops).status_code == 200


def _make_due(user_id: Any) -> None:
    with get_sessionmaker()() as db:
        db.execute(
            text("update mistake_entry set due_at = now() - interval '1 minute' where user_id = :u"),
            {"u": str(user_id)},
        )
        db.commit()


def test_wrong_answers_are_collected_and_review_follows_the_spacing(
    client: TestClient, physics: dict[str, Any]
) -> None:
    learner = _learner(client)
    form = _form(client, learner, physics["chapter"], count=POOL).json()
    attempt = _start(client, learner, form["id"])
    _answer(client, learner, form["id"], attempt, correct={1})
    _submit(client, learner, attempt["id"])
    book = client.get("/v1/me/notebook", headers=learner.headers).json()
    assert len(book) == POOL - 1 and all(e["status"] == "open" and not e["due"] for e in book)
    assert "after 1 day" in book[0]["why"] and book[0]["stem"]
    noted = client.put(
        f"/v1/me/notebook/{book[0]['id']}", headers=learner.headers, json={"note": "Fixture: recheck units"}
    )
    assert noted.json()["note"] == "Fixture: recheck units"
    other = _learner(client)
    assert client.put(f"/v1/me/notebook/{book[0]['id']}", headers=other.headers, json={"note": "x"}).status_code == 404
    review_url = "/v1/me/notebook/review"
    body = {"grade": 11, "subject": "physics", "count": 3}
    nothing = client.post(review_url, headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex}, json=body)
    assert nothing.status_code == 422 and nothing.json()["code_reason"] == "NOTHING_DUE"
    _make_due(learner.id)
    rv = client.post(review_url, headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex}, json=body).json()
    assert rv["question_count"] == 3 and rv["scope"]["mode"] == "review"
    ra = _start(client, learner, rv["id"])
    _answer(client, learner, rv["id"], ra, correct={1, 2})  # two right, one wrong again
    _submit(client, learner, ra["id"])
    after = {e["id"]: e for e in client.get("/v1/me/notebook", headers=learner.headers).json()}
    reviewed = [after[i] for i in rv["scope"]["entries"]]
    assert sorted(e["misses"] for e in reviewed) == [1, 1, 2]
    advanced = [e for e in reviewed if e["misses"] == 1]
    assert all("after 3 day" in e["why"] for e in advanced)  # moved to the next interval
    assert "after 1 day" in next(e for e in reviewed if e["misses"] == 2)["why"]  # missed again: reset


def test_a_voided_question_stays_in_the_notebook_with_its_reason(client: TestClient, physics: dict[str, Any]) -> None:
    learner = _learner(client)
    form = _form(client, learner, physics["chapter"], count=POOL).json()
    attempt = _start(client, learner, form["id"])
    _answer(client, learner, form["id"], attempt, correct=set())
    _submit(client, learner, attempt["id"])
    item = _form_item_ids(form["id"])[1]
    pub = physics["publisher"]
    with get_sessionmaker()() as db:
        adjudicator = Staff(client, db, ["academic_adjudicator"], {"grades": [11], "subjects": ["physics"]}, mfa=True)
    try:
        assert _post(client, pub, item, "quarantine", {"reason": "Fixture: void", "level": "VOID"}).status_code == 200
        done = client.post(
            f"/v1/studio/items/{item}/score-corrections",
            headers=adjudicator.headers,
            json={"defect": "VOID", "reason": "Fixture: no valid option"},
        )
        assert done.status_code == 201, done.text
        book = client.get("/v1/me/notebook", headers=learner.headers).json()
        voided = [e for e in book if e["status"] == "voided"]
        assert len(voided) == 1 and "withdrawn after academic review" in voided[0]["why"]
    finally:
        with get_sessionmaker()() as db:
            db.execute(text("update mcq_adjudication set status = 'superseded' where item_id = :i"), {"i": item})
            db.commit()
        _post(client, pub, item, "release", {"reason": "Fixture cleanup"})
