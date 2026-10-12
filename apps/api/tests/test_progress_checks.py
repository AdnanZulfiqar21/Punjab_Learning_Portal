"""P12.S4.T3 (DAYS-01): progress calculations and events hold up.

* Duplicates count once: a replayed answer, a replayed submission and its `attempt.submitted` event.
* A resumed attempt counts once, and only when submitted. Unanswered questions are not counted as answered.
* A regrade (a reviewed VOID correction) changes progress only through the latest score version; the first is kept.
* The dashboard and the progress report show the same records (web and mobile both read these two endpoints).
* Days follow Pakistan time (or the learner's own timezone), not the UTC database day.

Questions, answers and corrections are labelled technical fixtures.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, literal, select, text
from sqlalchemy.orm import Session

from portal_api import days
from portal_api.db import get_sessionmaker
from portal_api.modules.analytics.events import AnalyticsEvent
from tests.test_attempts import POOL, _form, _form_item_ids, _learner, _op, _save_ops, _start, publish_physics_pool
from tests.test_content_workflow import Staff, _post
from tests.test_mcq_corrections import _adjudicator, _correct, _keys
from tests.test_mistake_notebook import _answer


@pytest.fixture(scope="module")
def pool(client: TestClient) -> dict[str, Any]:
    """This module quarantines and corrects a question, so it publishes its own pool in another chapter (OCT9-05)."""
    return publish_physics_pool(client, 4)


def _progress(client: TestClient, who: Staff) -> dict[str, Any]:
    r = client.get("/v1/me/progress", headers=who.headers)
    assert r.status_code == 200, r.text
    return dict(r.json())


def _physics(report: dict[str, Any]) -> dict[str, Any] | None:
    return next((s for s in report["subjects"] if (s["grade"], s["subject"]) == (11, "physics")), None)


def _submit(client: TestClient, who: Staff, attempt_id: str, key: str | None = None) -> Any:
    return client.post(
        f"/v1/attempts/{attempt_id}/submit",
        headers=who.headers,
        json={"idempotency_key": key or uuid.uuid4().hex, "ops": []},
    )


def _agrees(client: TestClient, who: Staff, report: dict[str, Any]) -> None:
    """The dashboard's recent results are the progress report's, record for record."""
    dashboard = client.get("/v1/me/dashboard", headers=who.headers).json()
    assert dashboard["recent"] == report["recent"][:3]
    assert dashboard["results_pending"] == report["results_pending"]


def test_duplicates_count_once_and_a_resumed_attempt_counts_when_submitted(
    client: TestClient, pool: dict[str, Any]
) -> None:
    learner = _learner(client)
    form = _form(client, learner, pool["chapter"], count=POOL).json()
    attempt = _start(client, learner, form["id"])
    keys = _keys(form["id"])
    first = _op(1, 1, keys[1])
    for _ in range(2):  # a replayed answer (same operation id) is one answer
        assert _save_ops(client, learner, attempt["id"], first).status_code == 200
    assert _physics(_progress(client, learner)) is None  # an open attempt adds nothing yet

    # Resumed later: the saved answer is still there; one more question is answered wrongly, the rest left blank.
    resumed = client.get(f"/v1/attempts/{attempt['id']}", headers=learner.headers).json()
    assert {a["position"]: a["option_id"] for a in resumed["answers"]}[1] == keys[1]
    wrong = next(o for o in ("o1", "o2", "o3", "o4") if o != keys[2])
    assert _save_ops(client, learner, attempt["id"], _op(2, 1, wrong)).status_code == 200
    key = uuid.uuid4().hex
    for _ in range(2):  # a replayed submission
        assert _submit(client, learner, attempt["id"], key).status_code == 200

    report = _progress(client, learner)
    row = _physics(report)
    assert row is not None
    assert (row["tests"], row["questions_answered"], row["correct"], row["accuracy"]) == (1, 2, 1, 50.0)
    assert [r["attempt_id"] for r in report["recent"]] == [attempt["id"]]
    with get_sessionmaker()() as s:
        submitted = s.scalar(
            select(func.count()).where(AnalyticsEvent.user_id == learner.id, AnalyticsEvent.name == "attempt.submitted")
        )
    assert submitted == 1
    _agrees(client, learner, report)


def test_a_regrade_changes_progress_only_through_the_latest_score_version(
    client: TestClient, pool: dict[str, Any]
) -> None:
    learner = _learner(client)
    form = _form(client, learner, pool["chapter"], count=POOL).json()
    attempt = _start(client, learner, form["id"])
    _answer(client, learner, form["id"], attempt, correct={1, 2, 3})
    assert _submit(client, learner, attempt["id"]).status_code == 200
    before = _progress(client, learner)
    row = _physics(before)
    assert row is not None and (row["questions_answered"], row["correct"]) == (POOL, 3)
    _agrees(client, learner, before)

    item = _form_item_ids(form["id"])[1]  # answered correctly, then found to have no valid answer
    pub = pool["publisher"]
    try:
        assert _post(client, pub, item, "quarantine", {"reason": "Fixture: void", "level": "VOID"}).status_code == 200
        made = _correct(client, _adjudicator(client), item, defect="VOID", reason="Fixture: no valid option")
        assert made.status_code == 201, made.text

        after = _progress(client, learner)
        row = _physics(after)
        assert row is not None and (row["tests"], row["questions_answered"], row["correct"]) == (1, POOL - 1, 2)
        old, new = before["recent"][0], after["recent"][0]
        assert new["attempt_id"] == attempt["id"] and (old["score_version"], new["score_version"]) == (1, 2)
        assert (new["raw"], new["maximum"]) == (old["raw"] - 1, old["maximum"] - 1)
        _agrees(client, learner, after)
        with get_sessionmaker()() as s:
            kept = s.execute(
                text("select version, raw from score_version where attempt_id = :a order by version"),
                {"a": attempt["id"]},
            ).all()
        assert [tuple(k) for k in kept] == [(1, old["raw"]), (2, new["raw"])]  # the first version is kept
    finally:
        with get_sessionmaker()() as s:
            s.execute(text("update mcq_adjudication set status = 'superseded' where item_id = :i"), {"i": item})
            s.commit()
        _post(client, pub, item, "release", {"reason": "Fixture cleanup"})


def test_days_follow_pakistan_time_not_the_utc_database_day(client: TestClient, db: Session) -> None:
    late = datetime(2026, 10, 12, 20, 30, tzinfo=UTC)  # 01:30 on Tuesday 13 October in Pakistan
    assert late.date() == date(2026, 10, 12) and days.local_date(late) == date(2026, 10, 13)
    assert days.local_date(datetime(2026, 10, 12, 18, 59, tzinfo=UTC)) == date(2026, 10, 12)  # 23:59 in Pakistan
    assert days.local_date(late, "Europe/London") == date(2026, 10, 12)  # a learner's own timezone
    # Report buckets: the Pakistan day, and the Pakistan week (Sunday 20:00 UTC is already Monday in Pakistan).
    assert db.scalar(select(days.day_of(literal(late)))) == datetime(2026, 10, 13)
    sunday_night = datetime(2026, 10, 18, 20, 0, tzinfo=UTC)
    assert db.scalar(select(days.week_of(literal(sunday_night)))) == datetime(2026, 10, 19)
    assert days.wall_clock(sunday_night) == datetime(2026, 10, 19, 1, 0)

    # The study plan starts on the learner's day, and that day isn't "in the future".
    learner = _learner(client)
    today = days.learner_today(db, learner.id)
    q: dict[str, Any] = {"grade": 11, "subject": "physics", "daily_minutes": 60}
    same_day = client.get("/v1/me/study-plan", headers=learner.headers, params={**q, "target_date": today.isoformat()})
    assert same_day.status_code == 422
    week = {**q, "target_date": (today + timedelta(days=7)).isoformat()}
    plan = client.get("/v1/me/study-plan", headers=learner.headers, params=week)
    assert plan.status_code == 200, plan.text
    assert plan.json()["schedule"][0]["date"] == today.isoformat()
