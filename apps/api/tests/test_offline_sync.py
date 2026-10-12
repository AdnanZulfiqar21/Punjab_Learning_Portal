"""P13.S3.T2 (OFFLINE-SYNC-01): progress written offline is replayed when the app is back online. A replay is safe:
the same note text sent again (its first response was lost) is accepted as already saved, never reported as a
conflict with the learner's own words; a genuinely different edit from a stale copy is still a conflict. Completing a
lesson twice at once (a queued replay racing a tap) leaves one completion and one learning event, never an error or a
duplicate. Fixture accounts and lessons only."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.test_attempts import _learner
from tests.test_content_workflow import Staff
from tests.test_study_tools import _live_lesson, _note, team  # noqa: F401 - the team fixture


def test_a_replayed_note_save_is_already_saved_not_a_conflict(
    client: TestClient,
    db: Session,
    team: dict[str, Staff],  # noqa: F811
) -> None:
    lesson = _live_lesson(client, db, team)
    me = _learner(client)
    first = _note(client, me, lesson, "Written on the bus.", 0)
    assert first.status_code == 200 and first.json()["revision"] == 1
    replay = _note(client, me, lesson, "Written on the bus.", 0)  # the same save, sent again from the queue
    assert replay.status_code == 200, replay.text
    assert replay.json()["revision"] == 1 and replay.json()["text"] == "Written on the bus."  # nothing written twice
    different = _note(client, me, lesson, "A different edit from an old copy.", 0)
    assert different.status_code == 409 and different.json()["code_reason"] == "NOTE_CHANGED"


def test_completing_a_lesson_twice_at_once_counts_once(
    client: TestClient,
    db: Session,
    team: dict[str, Staff],  # noqa: F811
) -> None:
    lesson = _live_lesson(client, db, team)
    me = _learner(client)
    barrier = threading.Barrier(4)

    def complete(_: int) -> int:
        barrier.wait()
        return client.post(f"/v1/me/lessons/{lesson}/complete", headers=me.headers).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        codes = list(pool.map(complete, range(4)))
    assert codes == [204, 204, 204, 204]
    rows = db.execute(
        text("select count(*) from lesson_completion where user_id = :u and item_id = :i"),
        {"u": str(me.id), "i": lesson},
    ).scalar_one()
    events = db.execute(
        text("select count(*) from analytics_event where user_id = :u and name = 'lesson.completed'"), {"u": str(me.id)}
    ).scalar_one()
    assert (rows, events) == (1, 1)
