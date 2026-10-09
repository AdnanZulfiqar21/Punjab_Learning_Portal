"""P09.S2/S3 (MOCK-01): mocks built from a published exam profile; honest per-section shortage; frozen policies.
Profiles and questions are technical fixtures, not official patterns or academic content."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests import test_attempts
from tests.test_attempts import _learner
from tests.test_content_workflow import Staff

physics = test_attempts.physics


def _publish_profile(client: TestClient, db: Session, sections: list[dict[str, Any]], **rules: Any) -> str:
    author = Staff(client, db, ["academic_adjudicator"], mfa=True)
    v1, v2 = Staff(client, db, ["academic_adjudicator"], mfa=True), Staff(client, db, ["owner_admin"], mfa=True)
    code = f"MOCKFIX-{uuid.uuid4().hex[:6].upper()}"
    made = client.post("/v1/admin/exam-profiles", headers=author.headers, json={"code": code, "name": "Fixture mock"})
    pid = next(p["id"] for p in made.json() if p["code"] == code)
    body = {
        "source_url": "https://example.invalid/fixture",
        "source_note": "Fixture: technical pattern for tests.",
        "duration_minutes": 30,
        "negative_marks": 1,
        "marks_per_question": 2,
        "sections": sections,
        **rules,
    }
    vid = client.post(
        f"/v1/admin/exam-profiles/{pid}/versions", headers=author.headers, json={"year": 2026, "rules": body}
    ).json()["id"]
    for who in (v1, v2):
        client.post(
            f"/v1/admin/exam-profile-versions/{vid}/verify",
            headers=who.headers,
            json={"note": "Fixture verification note"},
        )
    assert client.post(f"/v1/admin/exam-profile-versions/{vid}/publish", headers=v1.headers).status_code == 200
    return code


def _mock(client: TestClient, who: Any, code: str, key: str | None = None) -> Any:
    return client.post(
        "/v1/mocks", headers={**who.headers, "Idempotency-Key": key or uuid.uuid4().hex}, json={"code": code}
    )


def test_a_mock_freezes_the_profile_and_its_policies(client: TestClient, db: Session, physics: dict[str, Any]) -> None:
    code = _publish_profile(client, db, [{"subject": "physics", "grades": [11], "questions": 3}])
    learner = _learner(client)
    ready = client.get(f"/v1/mocks/{code}/readiness", headers=learner.headers).json()
    assert ready["ready"] is True and ready["sections"][0]["available"] >= 3
    key = uuid.uuid4().hex
    r = _mock(client, learner, code, key)
    assert r.status_code == 201, r.text
    form = r.json()
    assert form["question_count"] == 3 and form["duration_s"] == 1800 and form["negative_marks"] == 1
    assert form["late_write_tolerance_ms"] == 0 and form["scope"]["mode"] == "mock" and form["scope"]["profile"] == code
    assert form["scope"]["sections"] == [{"subject": "physics", "grades": [11], "from": 1, "to": 3}]
    assert _mock(client, learner, code, key).json()["id"] == form["id"]  # idempotent
    attempt = client.post(f"/v1/practice/forms/{form['id']}/attempt", headers=learner.headers).json()
    assert len(attempt["items"]) == 3 and all(i["marks"] == 2 for i in attempt["items"]) and attempt["deadline_at"]


def test_a_short_pool_blocks_the_mock_with_every_sections_numbers(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    code = _publish_profile(
        client,
        db,
        [
            {"subject": "physics", "grades": [11], "questions": 2},
            {"subject": "mathematics", "grades": [12], "questions": 400},
        ],
    )
    learner = _learner(client)
    r = _mock(client, learner, code)
    assert r.status_code == 422 and r.json()["code_reason"] == "POOL_SHORTAGE"
    assert [s["subject"] for s in r.json()["sections"]] == ["mathematics"] and r.json()["sections"][0][
        "required"
    ] == 400
    assert client.get(f"/v1/mocks/{code}/readiness", headers=learner.headers).json()["ready"] is False
    scheduled = _publish_profile(
        client, db, [{"subject": "physics", "grades": [11], "questions": 1}], solution_release="after_window"
    )
    s = _mock(client, learner, scheduled)
    assert s.status_code == 409 and s.json()["code_reason"] == "MOCK_SCHEDULED"
    assert _mock(client, learner, "NO-SUCH-PATTERN").status_code == 404


def test_rehearsal_interrupted_mock(client: TestClient, db: Session, physics: dict[str, Any]) -> None:
    """Runbook `interrupted-mock.md`: saved answers survive a lost connection; reopening resumes the same attempt
    within the time; after the cutoff the server finalises it with every answer saved before then; the learner can
    take a fresh mock. No staff action or database edit is needed."""
    from tests.test_attempts import _op, _save_ops, _set_times

    code = _publish_profile(client, db, [{"subject": "physics", "grades": [11], "questions": 3}])
    learner = _learner(client)
    form = _mock(client, learner, code).json()
    attempt = client.post(f"/v1/practice/forms/{form['id']}/attempt", headers=learner.headers).json()
    first = attempt["items"][0]
    assert (
        _save_ops(client, learner, attempt["id"], _op(first["position"], 1, first["options"][0]["id"])).status_code
        == 200
    )
    # The connection drops. Reopening within the time resumes the same attempt with the answer kept.
    resumed = client.post(f"/v1/practice/forms/{form['id']}/attempt", headers=learner.headers).json()
    assert resumed["id"] == attempt["id"]
    assert client.get(f"/v1/attempts/{attempt['id']}", headers=learner.headers).json()["status"] == "active"
    # The learner only comes back after the cutoff: the server finalises with the saved answer counted.
    _set_times(attempt["id"], deadline_offset_s=-10, cutoff_offset_s=-1)
    after = client.get(f"/v1/attempts/{attempt['id']}", headers=learner.headers).json()
    assert after["status"] == "finalised" and after["receipt"]["reason"] == "expiry"
    assert after["receipt"]["answered_count"] == 1
    assert client.get(f"/v1/attempts/{attempt['id']}/result", headers=learner.headers).status_code == 200
    assert _mock(client, learner, code).status_code == 201  # a fresh mock is always available
