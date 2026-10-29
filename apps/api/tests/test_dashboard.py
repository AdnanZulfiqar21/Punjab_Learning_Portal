"""P11.S1.T2 (DASHBOARD-01): the learner dashboard. The three progress meters are kept separate and defined:
syllabus coverage (profile outcomes with live content, from verified inclusion records), content completed (lessons
completed out of live lessons in scope) and demonstrated knowledge (topics the evidence rules classify demonstrated).
A zero denominator or a missing profile shows "unavailable", never an invented percentage. The dashboard also shows
what to continue, today's revision, the next scheduled mock and recent results. Fixture accounts and content only."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests import test_content_workflow
from tests.test_attempts import POOL, _form, _learner, _start
from tests.test_content_workflow import Staff, _confirm_rights, _post, _submitted
from tests.test_mistake_notebook import _answer, _make_due, _submit

URL = "/v1/me/dashboard"
team = test_content_workflow.team


def _meters(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {m["key"]: m for m in body["meters"]}


def test_meters_are_unavailable_without_a_profile(client: TestClient) -> None:
    learner = _learner(client)
    r = client.get(URL, headers=learner.headers)
    assert r.status_code == 200, r.text
    meters = _meters(r.json())
    assert set(meters) == {"syllabus_coverage", "content_completed", "demonstrated_knowledge"}
    for m in meters.values():
        assert m["percent"] is None and m["unavailable"] and m["definition"]
    assert r.headers["cache-control"].startswith("private")


def test_the_dashboard_reflects_real_records(client: TestClient, physics: dict[str, Any]) -> None:
    learner = _learner(client)
    profile = client.put("/v1/me/profile", headers=learner.headers, json={"grade": 11, "subjects": ["physics"]})
    assert profile.status_code == 200, profile.text
    form = _form(client, learner, physics["chapter"], count=POOL).json()
    attempt = _start(client, learner, form["id"])
    _answer(client, learner, form["id"], attempt, correct={1})
    _submit(client, learner, attempt["id"])
    _make_due(learner.id)

    body = client.get(URL, headers=learner.headers).json()
    meters = _meters(body)
    for m in meters.values():  # consistent fractions, or an explicit reason
        if m["percent"] is None:
            assert m["unavailable"]
        else:
            assert 0 <= m["numerator"] <= m["denominator"] and m["denominator"] > 0
            assert m["percent"] == round(100 * m["numerator"] / m["denominator"], 1)
    # No verified inclusion records yet (P05.S2, B02): coverage is unavailable; book topics aren't syllabus.
    assert meters["syllabus_coverage"]["percent"] is None and "verified" in meters["syllabus_coverage"]["unavailable"]
    demonstrated = meters["demonstrated_knowledge"]  # one chapter-level test classifies no topic: no invented 0%
    assert demonstrated["percent"] is None and demonstrated["unavailable"].startswith("Not enough evidence yet")
    assert meters["content_completed"]["percent"] is None  # no live Physics 11 lessons: unavailable, not 0%

    notebook = client.get("/v1/me/notebook", headers=learner.headers).json()
    assert body["revision"]["due"] == sum(1 for e in notebook if e["due"]) and body["revision"]["due"] > 0
    assert [r["attempt_id"] for r in body["recent"]][:1] == [attempt["id"]]
    assert body["profile"] == {"grade": 11, "subjects": ["physics"]}


def test_continue_learning_and_content_completed_follow_lessons(
    client: TestClient, db: Session, team: dict[str, Staff]
) -> None:
    item, _, doc = _submitted(client, db, team)
    _confirm_rights(client, db, doc)
    approve = {"decision": "approve", "comment": "Fixture check"}
    assert _post(client, team["reviewer"], item["id"], "review", approve).status_code == 200
    assert _post(client, team["publisher"], item["id"], "publish").status_code == 200
    learner = _learner(client)
    client.put("/v1/me/profile", headers=learner.headers, json={"grade": 11, "subjects": ["biology"]})
    opened = client.post("/v1/me/events/lesson-started", headers=learner.headers, json={"lesson_id": item["id"]})
    assert opened.status_code == 204, opened.text

    body = client.get(URL, headers=learner.headers).json()
    assert body["continue_learning"]["lesson_id"] == item["id"]
    before = _meters(body)["content_completed"]
    assert before["denominator"] >= 1

    assert client.post(f"/v1/me/lessons/{item['id']}/complete", headers=learner.headers).status_code == 204
    body = client.get(URL, headers=learner.headers).json()
    after = _meters(body)["content_completed"]
    assert after["numerator"] == before["numerator"] + 1 and after["denominator"] == before["denominator"]
    assert (body["continue_learning"] or {}).get("lesson_id") != item["id"]  # completed lessons aren't "continue"

    client.delete(f"/v1/me/lessons/{item['id']}/complete", headers=learner.headers)
    client.put("/v1/me/profile", headers=learner.headers, json={"grade": 12, "subjects": ["biology"]})
    body = client.get(URL, headers=learner.headers).json()
    assert body["continue_learning"] is None  # a Class 11 lesson never appears on a Class 12 dashboard
