"""P09.S2.T3 (SCHEDULE-01): scheduled mock windows, late-entry policies, accommodations and held results.
Fixture profiles and questions only. Session times are moved with SQL purely as test setup."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from tests import test_attempts
from tests.test_attempts import _learner
from tests.test_content_workflow import Staff
from tests.test_mocks import _publish_profile

physics = test_attempts.physics


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _schedule(client: TestClient, admin: Staff, code: str, late_entry: str = "fixed_end") -> dict[str, Any]:
    now = datetime.now(UTC)
    body = {
        "profile_code": code,
        "title": f"Fixture scheduled mock {uuid.uuid4().hex[:8]}",
        "starts_at": _iso(now + timedelta(hours=1)),
        "entry_closes_at": _iso(now + timedelta(hours=1, minutes=15)),
        "window_closes_at": _iso(now + timedelta(hours=2)),
        "results_at": _iso(now + timedelta(hours=3)),
        "late_entry": late_entry,
    }
    r = client.post("/v1/admin/mock-sessions", headers=admin.headers, json=body)
    assert r.status_code == 201, r.text
    return dict(next(s for s in r.json() if s["title"] == body["title"]))


def _shift(session_id: str, **offsets_min: float) -> None:
    sets = ", ".join(f"{k} = clock_timestamp() + make_interval(secs => 60 * :{k})" for k in offsets_min)
    with get_sessionmaker()() as db:
        db.execute(text(f"update mock_session set {sets} where id = :id"), {"id": session_id, **offsets_min})  # noqa: S608
        db.commit()


def _duration(attempt_id: str) -> float:
    with get_sessionmaker()() as db:
        row = db.execute(
            text("select extract(epoch from deadline_at - started_at) from attempt where id = :a"), {"a": attempt_id}
        ).scalar_one()
        return float(row)


def test_schedule_rules(client: TestClient, db: Session, physics: dict[str, Any]) -> None:
    code = _publish_profile(
        client, db, [{"subject": "physics", "grades": [11], "questions": 2}], solution_release="after_window"
    )
    admin = Staff(client, db, ["academic_adjudicator"], mfa=True)
    now = datetime.now(UTC)
    base = {
        "profile_code": code,
        "title": "Fixture",
        "starts_at": _iso(now - timedelta(minutes=5)),
        "entry_closes_at": _iso(now + timedelta(minutes=10)),
        "window_closes_at": _iso(now + timedelta(hours=1)),
        "results_at": _iso(now + timedelta(hours=2)),
    }
    assert client.post("/v1/admin/mock-sessions", headers=admin.headers, json=base).status_code == 422  # past start
    short = {
        **base,
        "starts_at": _iso(now + timedelta(minutes=5)),
        "window_closes_at": _iso(now + timedelta(minutes=20)),
    }
    assert client.post("/v1/admin/mock-sessions", headers=admin.headers, json=short).status_code == 422  # < 30 min
    early = {**base, "starts_at": _iso(now + timedelta(minutes=5)), "results_at": _iso(now + timedelta(minutes=30))}
    assert client.post("/v1/admin/mock-sessions", headers=admin.headers, json=early).status_code == 422
    learner = _learner(client)
    assert client.post("/v1/admin/mock-sessions", headers=learner.headers, json=base).status_code == 403


def test_fixed_end_accommodation_and_held_results(client: TestClient, db: Session, physics: dict[str, Any]) -> None:
    code = _publish_profile(
        client, db, [{"subject": "physics", "grades": [11], "questions": 2}], solution_release="after_window"
    )
    admin = Staff(client, db, ["academic_adjudicator"], mfa=True)
    session = _schedule(client, admin, code)
    a, b = _learner(client), _learner(client)
    join = f"/v1/mock-sessions/{session['id']}/join"
    early = client.post(join, headers=a.headers)
    assert early.status_code == 409 and early.json()["code_reason"] == "NOT_STARTED"
    acc = client.post(
        f"/v1/admin/mock-sessions/{session['id']}/accommodations",
        headers=admin.headers,
        json={"email": b.email, "extra_minutes": 15, "reason": "Fixture: documented extra time"},
    )
    assert acc.status_code == 204
    # Started ten minutes ago with a fixed end: 30-minute test, so about 20 minutes remain.
    _shift(session["id"], starts_at=-10, entry_closes_at=5, window_closes_at=50, results_at=60)
    ja = client.post(join, headers=a.headers)
    assert ja.status_code == 200, ja.text
    assert 1100 < _duration(ja.json()["attempt_id"]) < 1250
    assert client.post(join, headers=a.headers).json()["attempt_id"] == ja.json()["attempt_id"]  # once
    jb = client.post(join, headers=b.headers).json()
    assert 1100 + 900 < _duration(jb["attempt_id"]) < 1250 + 900  # plus the 15-minute accommodation
    sub = client.post(
        f"/v1/attempts/{ja.json()['attempt_id']}/submit",
        headers=a.headers,
        json={"idempotency_key": uuid.uuid4().hex, "ops": []},
    )
    assert sub.status_code == 200
    held = client.get(f"/v1/attempts/{ja.json()['attempt_id']}/result", headers=a.headers)
    assert held.status_code == 409 and held.json()["code_reason"] == "RESULTS_PENDING"
    _shift(session["id"], results_at=-1)
    assert client.get(f"/v1/attempts/{ja.json()['attempt_id']}/result", headers=a.headers).status_code == 200
    # Late entry closed: a newcomer can't join; someone already in can still come back.
    _shift(session["id"], entry_closes_at=-1)
    late = client.post(join, headers=_learner(client).headers)
    assert late.status_code == 409 and late.json()["code_reason"] == "ENTRY_CLOSED"
    assert client.post(join, headers=b.headers).json()["attempt_id"] == jb["attempt_id"]


def test_full_duration_is_capped_by_the_window_and_cancel_only_before_start(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    code = _publish_profile(
        client, db, [{"subject": "physics", "grades": [11], "questions": 2}], solution_release="after_window"
    )
    admin = Staff(client, db, ["academic_adjudicator"], mfa=True)
    session = _schedule(client, admin, code, late_entry="full_duration")
    other = _schedule(client, admin, code)
    _shift(session["id"], starts_at=-5, entry_closes_at=10, window_closes_at=12, results_at=60)
    j = client.post(f"/v1/mock-sessions/{session['id']}/join", headers=_learner(client).headers)
    assert j.status_code == 200 and 650 < _duration(j.json()["attempt_id"]) < 760  # capped at the window (~12 min)
    cancel = {"reason": "Fixture: cancelled before start"}
    assert (
        client.post(f"/v1/admin/mock-sessions/{other['id']}/cancel", headers=admin.headers, json=cancel).status_code
        == 204
    )
    assert (
        client.post(f"/v1/admin/mock-sessions/{session['id']}/cancel", headers=admin.headers, json=cancel).status_code
        == 409
    )
    listed = [s["id"] for s in client.get("/v1/mock-sessions", headers=_learner(client).headers).json()]
    assert session["id"] in listed and other["id"] not in listed
