"""P11.S2.T1 (LESSON-PROGRESS-01): lesson progress across devices never moves backwards because of an old event.

* A completion or its undo may arrive late (queued offline on a phone). Each carries when the learner acted; an event
  older than the lesson's last accepted one is ignored, so a stale undo never removes a newer completion made on
  another device, and a stale completion never reverses a newer undo. An immediate action counts as "now".
* "Continue reading" keeps the newest place in a chapter: an older position report never replaces a newer one, and a
  lesson that is no longer published is never offered.

Technical fixture lessons and labelled fixture accounts only.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests import test_content_workflow
from tests.test_attempts import _learner
from tests.test_content_workflow import Staff, _confirm_rights, _post, _submitted

team = test_content_workflow.team


def _published(client: TestClient, db: Session, team: dict[str, Staff]) -> tuple[str, Any]:
    item, chapter, doc = _submitted(client, db, team)
    _confirm_rights(client, db, doc)
    review = {"decision": "approve", "comment": "Fixture check"}
    assert _post(client, team["reviewer"], item["id"], "review", review).status_code == 200
    assert _post(client, team["publisher"], item["id"], "publish").status_code == 200
    return str(item["id"]), chapter


def _at(minutes_ago: int) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes_ago)).isoformat()


def test_a_late_event_never_reverses_a_newer_completion(
    client: TestClient, db: Session, team: dict[str, Staff]
) -> None:
    lesson, chapter = _published(client, db, team)
    learner = _learner(client)
    url = f"/v1/me/lessons/{lesson}/complete"
    done = f"/v1/me/chapters/{chapter.id}/completed-lessons"

    assert client.post(url, headers=learner.headers).status_code == 204  # completed on the web, now
    stale_undo = client.delete(url, params={"client_at": _at(60)}, headers=learner.headers)  # an hour-old phone undo
    assert stale_undo.status_code == 204
    assert client.get(done, headers=learner.headers).json() == [lesson]  # still completed

    assert client.delete(url, params={"client_at": _at(0)}, headers=learner.headers).status_code == 204  # a newer undo
    assert client.get(done, headers=learner.headers).json() == []
    assert client.post(url, params={"client_at": _at(30)}, headers=learner.headers).status_code == 204  # stale again
    assert client.get(done, headers=learner.headers).json() == []  # the newer undo stands

    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()  # a fast phone clock counts as now
    assert client.post(url, params={"client_at": future}, headers=learner.headers).status_code == 204
    assert client.get(done, headers=learner.headers).json() == [lesson]


def test_continue_reading_keeps_the_newest_place(client: TestClient, db: Session, team: dict[str, Staff]) -> None:
    first, chapter = _published(client, db, team)
    second, same = _published(client, db, team)
    assert same.id == chapter.id
    learner = _learner(client)
    where = f"/v1/me/chapters/{chapter.id}/reading-position"
    assert client.get(where, headers=learner.headers).json() is None

    put = client.put(
        "/v1/me/reading-position",
        headers=learner.headers,
        json={"lesson_id": second, "block_index": 3, "client_at": _at(1)},
    )
    assert put.status_code == 200 and put.json()["lesson_id"] == second
    older = client.put(
        "/v1/me/reading-position",
        headers=learner.headers,
        json={"lesson_id": first, "block_index": 0, "client_at": _at(20)},
    )
    assert older.status_code == 200 and older.json()["lesson_id"] == second  # an older report never moves it back
    got = client.get(where, headers=learner.headers).json()
    assert (got["lesson_id"], got["block_index"]) == (second, 3) and got["lesson_title"]

    no_plan = Staff(client, db, [])
    locked = client.put("/v1/me/reading-position", headers=no_plan.headers, json={"lesson_id": first})
    assert locked.status_code == 403  # premium lesson, no plan: nothing to read, nothing to save

    retired = _post(client, team["publisher"], second, "retire", {"reason": "Fixture: withdrawn lesson"})
    assert retired.status_code == 200, retired.text
    assert client.get(where, headers=learner.headers).json() is None  # never offer a withdrawn lesson
