"""OCT9-04: scheduled mock admission uses an absolute deadline, rechecked at the real start; accommodations can't pass
the results time; an interrupted join never grants extra time. Fixture profiles only; times moved with SQL as setup."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from portal_api.modules.assessment import attempts as attempts_module
from tests import test_attempts
from tests.test_attempts import _learner
from tests.test_content_workflow import Staff
from tests.test_mock_sessions import _duration, _iso, _schedule, _shift
from tests.test_mocks import _publish_profile

physics = test_attempts.physics


def _profile(client: TestClient, db: Session) -> tuple[str, Staff]:
    code = _publish_profile(
        client, db, [{"subject": "physics", "grades": [11], "questions": 2}], solution_release="after_window"
    )
    return code, Staff(client, db, ["academic_adjudicator"], mfa=True)


def test_late_entry_must_close_before_a_fixed_end(client: TestClient, db: Session, physics: dict[str, Any]) -> None:
    code, admin = _profile(client, db)  # 30-minute fixture profile
    now = datetime.now(UTC)
    body = {
        "profile_code": code,
        "title": "Fixture late entry after the fixed end",
        "starts_at": _iso(now + timedelta(hours=1)),
        "entry_closes_at": _iso(now + timedelta(hours=1, minutes=40)),
        "window_closes_at": _iso(now + timedelta(hours=2)),
        "results_at": _iso(now + timedelta(hours=3)),
        "late_entry": "fixed_end",
    }
    assert client.post("/v1/admin/mock-sessions", headers=admin.headers, json=body).status_code == 422


def test_no_time_left_is_refused_and_little_time_is_not_rounded_up(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    code, admin = _profile(client, db)
    session = _schedule(client, admin, code)
    join = f"/v1/mock-sessions/{session['id']}/join"
    _shift(session["id"], starts_at=-29.75, entry_closes_at=5, window_closes_at=50, results_at=60)
    short = client.post(join, headers=_learner(client).headers)
    assert short.status_code == 200 and _duration(short.json()["attempt_id"]) < 30  # ~15 s left, not a free minute
    _shift(session["id"], starts_at=-40)  # the fixed end has passed although entry is (wrongly) still open
    late = client.post(join, headers=_learner(client).headers)
    assert late.status_code == 409 and late.json()["code_reason"] == "ENTRY_CLOSED"


def test_accommodations_cannot_pass_the_results_time(client: TestClient, db: Session, physics: dict[str, Any]) -> None:
    code, admin = _profile(client, db)
    session = _schedule(client, admin, code)  # fixed end at +1h30, results at +3h
    b = _learner(client)
    url = f"/v1/admin/mock-sessions/{session['id']}/accommodations"
    too_long = {"email": b.email, "extra_minutes": 240, "reason": "Fixture: beyond the results time"}
    r = client.post(url, headers=admin.headers, json=too_long)
    assert r.status_code == 422, r.text
    ok = {"email": b.email, "extra_minutes": 60, "reason": "Fixture: documented extra time"}
    assert client.post(url, headers=admin.headers, json=ok).status_code == 204
    full = _schedule(client, admin, code, late_entry="full_duration")  # latest end is the window close (+2h)
    url_full = f"/v1/admin/mock-sessions/{full['id']}/accommodations"
    over = {"email": b.email, "extra_minutes": 61, "reason": "Fixture: past the results time"}
    assert client.post(url_full, headers=admin.headers, json=over).status_code == 422


def test_an_interrupted_join_never_extends_or_reopens_admission(
    client: TestClient, db: Session, physics: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    code, admin = _profile(client, db)
    session = _schedule(client, admin, code)
    learner = _learner(client)
    join = f"/v1/mock-sessions/{session['id']}/join"
    _shift(session["id"], starts_at=-1, entry_closes_at=5, window_closes_at=50, results_at=60)

    def crash(*_: Any, **__: Any) -> Any:
        raise RuntimeError("Fixture: process stopped after the form was saved")

    monkeypatch.setattr(attempts_module, "start", crash)
    with pytest.raises(RuntimeError):
        client.post(join, headers=learner.headers)
    monkeypatch.undo()
    with get_sessionmaker()() as s:
        form_id = s.execute(
            text("select id from practice_form where owner_id = :u and idempotency_key = :k"),
            {"u": str(learner.id), "k": f"session-{session['id']}"},
        ).scalar_one()
    _shift(session["id"], starts_at=-10)  # the retry comes later: the fixed end doesn't move
    retry = client.post(join, headers=learner.headers)
    assert retry.status_code == 200 and 1100 < _duration(retry.json()["attempt_id"]) < 1250  # ~20 min, not 30

    other = _learner(client)
    monkeypatch.setattr(attempts_module, "start", crash)
    with pytest.raises(RuntimeError):
        client.post(join, headers=other.headers)
    monkeypatch.undo()
    with get_sessionmaker()() as s:
        other_form = s.execute(
            text("select id from practice_form where owner_id = :u and idempotency_key = :k"),
            {"u": str(other.id), "k": f"session-{session['id']}"},
        ).scalar_one()
    _shift(session["id"], entry_closes_at=-1)  # entry closed before the retry
    assert client.post(join, headers=other.headers).json()["code_reason"] == "ENTRY_CLOSED"
    direct = client.post(f"/v1/practice/forms/{other_form}/attempt", headers=other.headers)
    assert direct.status_code == 409 and direct.json()["code_reason"] == "ENTRY_CLOSED"
    assert form_id != other_form
