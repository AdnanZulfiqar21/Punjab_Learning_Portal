"""P09.S3.T3 (FIXED-FORMS-01): a scheduled mock session gives every participant the same fixed form (question
versions, order and option permutations); a practice mock stays varied per learner; a lost race to become the master
is resolved without two forms. Fixture profile and physics fixture questions only."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from portal_api.modules.assessment import sessions
from tests.test_attempts import _learner
from tests.test_content_workflow import Staff
from tests.test_mock_sessions import _schedule, _shift
from tests.test_mocks import _publish_profile


def _items(attempt_id: str) -> list[tuple[int, str, str]]:
    with get_sessionmaker()() as db:
        rows = db.execute(
            text(
                "select i.position, i.version_id::text, i.option_order::text from form_item i "
                "join attempt a on a.form_id = i.form_id where a.id = :a order by i.position"
            ),
            {"a": attempt_id},
        ).all()
    return [(p, v, o) for p, v, o in rows]


def _scope(attempt_id: str) -> dict[str, Any]:
    with get_sessionmaker()() as db:
        return dict(
            db.execute(
                text("select f.scope from practice_form f join attempt a on a.form_id = f.id where a.id = :a"),
                {"a": attempt_id},
            ).scalar_one()
        )


def test_every_participant_gets_the_same_fixed_form(client: TestClient, db: Session, physics: dict[str, Any]) -> None:
    code = _publish_profile(client, db, [{"subject": "physics", "grades": [11], "questions": 3}])
    admin = Staff(client, db, ["academic_adjudicator"], mfa=True)
    session = _schedule(client, admin, code)
    _shift(session["id"], starts_at=-1, entry_closes_at=10, window_closes_at=60, results_at=90)
    join = f"/v1/mock-sessions/{session['id']}/join"
    learners = [_learner(client) for _ in range(3)]
    attempts = []
    for who in learners:
        r = client.post(join, headers=who.headers)
        assert r.status_code == 200, r.text
        attempts.append(r.json()["attempt_id"])
    first = _items(attempts[0])
    assert len(first) == 3
    assert all(_items(a) == first for a in attempts[1:])  # same versions, order and option permutations
    assert _scope(attempts[0])["form_type"] == "fixed"
    assert _scope(attempts[1])["fixed_from"] and "fixed_from" not in _scope(attempts[0])
    master = db.execute(text("select master_form_id from mock_session where id = :s"), {"s": session["id"]}).scalar()
    assert master is not None


def test_a_practice_mock_stays_varied(client: TestClient, db: Session, physics: dict[str, Any]) -> None:
    code = _publish_profile(client, db, [{"subject": "physics", "grades": [11], "questions": 2}])
    who = _learner(client)
    r = client.post(
        "/v1/mocks", headers={**who.headers, "Idempotency-Key": "fixture-varied-" + code}, json={"code": code}
    )
    assert r.status_code in (200, 201), r.text
    form_scope = r.json()["scope"]
    assert form_scope["form_type"] == "varied"


def test_only_one_form_wins_the_race_to_be_the_master(client: TestClient, db: Session, physics: dict[str, Any]) -> None:
    code = _publish_profile(client, db, [{"subject": "physics", "grades": [11], "questions": 2}])
    admin = Staff(client, db, ["academic_adjudicator"], mfa=True)
    session = _schedule(client, admin, code)
    with get_sessionmaker()() as s:
        forms = s.execute(text("select id from practice_form order by created_at desc limit 2")).scalars().all()
        a, b = forms[0], forms[1]
        assert sessions.claim_master(s, session["id"], a) is True
        assert sessions.claim_master(s, session["id"], b) is False  # the second first-join loses and copies instead
        assert str(
            s.execute(text("select master_form_id from mock_session where id = :i"), {"i": session["id"]}).scalar()
        ) == str(a)
        s.execute(text("update mock_session set master_form_id = null where id = :i"), {"i": session["id"]})
        s.commit()
