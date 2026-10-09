"""OCT9-02: a score correction re-derives the notebook in the original chronology; it is never a new response.

A new score version is written directly (as a reviewed correction would) and the real `notebook.apply_attempt` runs
against PostgreSQL. Technical fixture questions only.
"""

from __future__ import annotations

import threading
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from portal_api.db import get_sessionmaker
from portal_api.modules.assessment import notebook
from portal_api.modules.assessment.models import Attempt, FormItem, ScoreVersion
from portal_api.modules.assessment.notebook import NO_LONGER_A_MISTAKE, MistakeEntry
from tests.test_attempts import POOL, _form, _learner, _start
from tests.test_mistake_notebook import _answer, _make_due, _submit


def _rescore(attempt_id: str, flip: dict[int, bool]) -> None:
    """Write a new latest score version with some positions' correctness changed, then apply it (as rescore does)."""
    with get_sessionmaker()() as db:
        attempt = db.get(Attempt, uuid.UUID(attempt_id))
        assert attempt is not None
        latest = db.scalars(
            select(ScoreVersion).where(ScoreVersion.attempt_id == attempt.id).order_by(ScoreVersion.version.desc())
        ).first()
        assert latest is not None
        items = [{**r, "correct": flip.get(int(r["position"]), r["correct"])} for r in latest.items]
        db.add(
            ScoreVersion(
                attempt_id=attempt.id,
                version=latest.version + 1,
                scoring_policy_version=latest.scoring_policy_version,
                adjudication_hash=f"fixture-{uuid.uuid4().hex[:8]}",
                status=latest.status,
                raw=latest.raw,
                maximum=latest.maximum,
                percentage=latest.percentage,
                items=items,
                reason="Fixture correction",
            )
        )
        db.flush()
        notebook.apply_attempt(db, attempt, db.execute(select(func.now())).scalar_one())
        db.commit()


def _state(user_id: Any) -> dict[uuid.UUID, tuple[Any, ...]]:
    with get_sessionmaker()() as db:
        return {
            e.family_id: (e.status, e.misses, e.interval_index, e.due_at, e.last_event_at, e.void_reason, e.note)
            for e in db.scalars(select(MistakeEntry).where(MistakeEntry.user_id == user_id))
        }


def _family(form_id: str, position: int) -> uuid.UUID:
    with get_sessionmaker()() as db:
        fam = db.scalar(
            select(FormItem.family_id).where(FormItem.form_id == uuid.UUID(form_id), FormItem.position == position)
        )
        assert fam is not None
        return fam


def test_a_correction_changes_only_the_corrected_question_and_replays_idempotently(
    client: TestClient, physics: dict[str, Any]
) -> None:
    learner = _learner(client)
    form = _form(client, learner, physics["chapter"], count=POOL).json()
    attempt = _start(client, learner, form["id"])
    _answer(client, learner, form["id"], attempt, correct=set())
    _submit(client, learner, attempt["id"])
    first = client.get("/v1/me/notebook", headers=learner.headers).json()
    client.put(f"/v1/me/notebook/{first[0]['id']}", headers=learner.headers, json={"note": "Fixture: keep me"})
    before = _state(learner.id)
    a, b = _family(form["id"], 1), _family(form["id"], 2)

    _rescore(attempt["id"], {})  # same answers re-scored: nothing moves
    assert _state(learner.id) == before

    _rescore(attempt["id"], {1: True})  # wrong -> correct for question A only
    after = _state(learner.id)
    assert after[a][0] == "voided" and after[a][5] == NO_LONGER_A_MISTAKE
    assert after[b] == before[b]  # question B: misses, interval and due date unchanged
    assert {k: v for k, v in after.items() if k != a} == {k: v for k, v in before.items() if k != a}
    assert any(v[6] == "Fixture: keep me" for v in after.values())  # private note survives
    _rescore(attempt["id"], {})  # replaying the same correction changes nothing further
    assert _state(learner.id) == after

    _rescore(attempt["id"], {1: False})  # correct -> wrong again: restored in the original chronology
    assert _state(learner.id)[a][:5] == before[a][:5]


def test_an_old_attempt_corrected_after_newer_reviews_keeps_the_review_progress(
    client: TestClient, physics: dict[str, Any]
) -> None:
    learner = _learner(client)
    form = _form(client, learner, physics["chapter"], count=POOL).json()
    attempt = _start(client, learner, form["id"])
    _answer(client, learner, form["id"], attempt, correct=set())
    _submit(client, learner, attempt["id"])
    _make_due(learner.id)
    body = {"grade": 11, "subject": "physics", "count": POOL}
    rv = client.post(
        "/v1/me/notebook/review", headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex}, json=body
    ).json()
    ra = _start(client, learner, rv["id"])
    _answer(client, learner, rv["id"], ra, correct=set(range(1, POOL + 1)))  # every review answer right
    _submit(client, learner, ra["id"])
    reviewed = _state(learner.id)
    assert all(v[0] == "open" and v[2] == 1 and v[1] == 1 for v in reviewed.values())

    _rescore(attempt["id"], {})  # the old attempt is re-scored after the review: review progress is kept
    assert _state(learner.id) == reviewed

    _rescore(ra["id"], {})  # re-scoring the review itself doesn't advance the interval again
    assert _state(learner.id) == reviewed


def test_concurrent_reconciliation_creates_no_duplicates(client: TestClient, physics: dict[str, Any]) -> None:
    learner = _learner(client)
    form = _form(client, learner, physics["chapter"], count=POOL).json()
    attempt = _start(client, learner, form["id"])
    _answer(client, learner, form["id"], attempt, correct=set())
    _submit(client, learner, attempt["id"])
    with get_sessionmaker()() as db:
        db.execute(MistakeEntry.__table__.delete().where(MistakeEntry.user_id == learner.id))
        db.commit()
    errors: list[BaseException] = []

    def run() -> None:
        try:
            with get_sessionmaker()() as db:
                a = db.get(Attempt, uuid.UUID(attempt["id"]))
                assert a is not None
                notebook.apply_attempt(db, a, db.execute(select(func.now())).scalar_one())
                db.commit()
        except BaseException as e:
            errors.append(e)

    threads = [threading.Thread(target=run) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(_state(learner.id)) == POOL
