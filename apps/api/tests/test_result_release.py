"""OCT9-01: a scheduled mock's results stay private on every learner surface until the session's live release time.

Result, reveal, progress, notebook, evidence, study plan, notifications and the personal-data export all follow one
policy (`sessions.held_forms`). The receipt and the learner's own submitted answers stay available. Technical fixture
questions only; session times are moved with SQL purely as test setup.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from tests.test_attempts import _learner, _op, _save_ops
from tests.test_content_workflow import Staff
from tests.test_mcq_corrections import _keys
from tests.test_mock_sessions import _schedule, _shift
from tests.test_mocks import _publish_profile


def _form_of(attempt_id: str) -> str:
    with get_sessionmaker()() as db:
        return str(db.execute(text("select form_id from attempt where id = :a"), {"a": attempt_id}).scalar_one())


def _sit(client: TestClient, db: Session, who: Any, *, admin: Staff, code: str) -> tuple[str, str, str]:
    """Join a started session, answer position 1 right and the rest wrong, submit. Returns (session, attempt, form)."""
    session = _schedule(client, admin, code)
    _shift(session["id"], starts_at=-5, entry_closes_at=10, window_closes_at=50, results_at=60)
    attempt_id = client.post(f"/v1/mock-sessions/{session['id']}/join", headers=who.headers).json()["attempt_id"]
    form_id = _form_of(attempt_id)
    keys = _keys(form_id)
    attempt = client.get(f"/v1/attempts/{attempt_id}", headers=who.headers).json()
    ops = []
    for item in attempt["items"]:
        p = item["position"]
        wrong = next(o["id"] for o in item["options"] if o["id"] != keys[p])
        ops.append(_op(p, 1, keys[p] if p == 1 else wrong))
    assert _save_ops(client, who, attempt_id, *ops).status_code == 200
    sub = client.post(
        f"/v1/attempts/{attempt_id}/submit", headers=who.headers, json={"idempotency_key": uuid.uuid4().hex, "ops": []}
    )
    assert sub.status_code == 200, sub.text
    return session["id"], attempt_id, form_id


def _surfaces(client: TestClient, who: Any, attempt_id: str) -> dict[str, Any]:
    h = who.headers
    plan_q = {"grade": 11, "subject": "physics", "daily_minutes": 60, "target_date": str(date.today() + timedelta(30))}
    export = client.get("/v1/me/data-export", headers=h)
    assert export.status_code == 200, export.text
    return {
        "result": client.get(f"/v1/attempts/{attempt_id}/result", headers=h),
        "reveal": client.post(f"/v1/attempts/{attempt_id}/items/1/reveal", headers=h),
        "progress": client.get("/v1/me/progress", headers=h).json(),
        "notebook": client.get("/v1/me/notebook", headers=h).json(),
        "evidence": client.get("/v1/me/evidence", headers=h, params={"grade": 11, "subject": "physics"}).json(),
        "plan": client.get("/v1/me/study-plan", headers=h, params=plan_q).json(),
        "export": json.loads(export.content),
        "notifications": client.get("/v1/me/notifications", headers=h).json(),
    }


def _assert_hidden(s: dict[str, Any], attempt_id: str) -> None:
    for k in ("result", "reveal"):
        assert s[k].status_code == 409 and s[k].json()["code_reason"] == "RESULTS_PENDING", (k, s[k].text)
    assert s["progress"]["subjects"] == [] and s["progress"]["recent"] == []
    assert s["progress"]["results_pending"] == 1
    assert s["notebook"] == []
    assert all(o["total_weight"] == 0 for o in s["evidence"]["outcomes"])
    assert all("No evidence yet" in x["why"] for x in s["plan"]["schedule"])
    practice = s["export"]["practice"]
    assert practice["scores"] == [] and practice["notebook"] == []
    assert [h["attempt_id"] for h in practice["results_pending"]] == [attempt_id]
    assert any(a["attempt_id"] == attempt_id for a in practice["answers"])  # own answers stay available
    assert all(n["event"] != "score.revised" for n in s["notifications"]["items"])


def test_held_results_leak_nowhere_until_the_live_release_time(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    code = _publish_profile(
        client, db, [{"subject": "physics", "grades": [11], "questions": 2}], solution_release="after_window"
    )
    admin = Staff(client, db, ["academic_adjudicator"], mfa=True)
    learner = _learner(client)
    session_id, attempt_id, _ = _sit(client, db, learner, admin=admin, code=code)
    receipt = client.get(f"/v1/attempts/{attempt_id}", headers=learner.headers)
    assert receipt.status_code == 200 and receipt.json()["status"] == "finalised"
    _assert_hidden(_surfaces(client, learner, attempt_id), attempt_id)
    _shift(session_id, results_at=120)  # staff postpone the release: still hidden
    _assert_hidden(_surfaces(client, learner, attempt_id), attempt_id)

    _shift(session_id, results_at=-1)
    s = _surfaces(client, learner, attempt_id)
    assert s["result"].status_code == 200 and s["reveal"].status_code == 200
    assert s["progress"]["results_pending"] == 0 and [r["attempt_id"] for r in s["progress"]["recent"]] == [attempt_id]
    assert len(s["notebook"]) == 1 and s["notebook"][0]["source_attempt_id"] == attempt_id
    assert any(o["total_weight"] > 0 for o in s["evidence"]["outcomes"])
    assert [x["attempt_id"] for x in s["export"]["practice"]["scores"]] == [attempt_id]
    assert len(s["export"]["practice"]["notebook"]) == 1 and s["export"]["practice"]["results_pending"] == []
    again = client.get("/v1/me/notebook", headers=learner.headers).json()
    assert again == s["notebook"]  # released exactly once: re-reading changes nothing


def test_an_unresolvable_session_reference_fails_closed(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    code = _publish_profile(
        client, db, [{"subject": "physics", "grades": [11], "questions": 2}], solution_release="after_window"
    )
    admin = Staff(client, db, ["academic_adjudicator"], mfa=True)
    learner = _learner(client)
    session_id, attempt_id, form_id = _sit(client, db, learner, admin=admin, code=code)
    _shift(session_id, results_at=-1)
    with get_sessionmaker()() as s:
        s.execute(
            text(
                "update practice_form set scope = jsonb_set(scope, '{session_id}', to_jsonb(cast(:sid as text))) "
                "where id = :f"
            ),
            {"sid": str(uuid.uuid4()), "f": form_id},
        )
        s.commit()
    r = client.get(f"/v1/attempts/{attempt_id}/result", headers=learner.headers)
    assert r.status_code == 409 and r.json()["code_reason"] == "RESULTS_PENDING"
    assert client.get("/v1/me/progress", headers=learner.headers).json()["results_pending"] == 1
