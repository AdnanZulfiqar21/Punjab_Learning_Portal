"""P12.S4.T1 (STUDYPLAN-01): honest shortfall, weakest evidence first, never splits or invents completion."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient

from portal_api.modules.assessment.plan import DEVELOPING_MINUTES, NO_EVIDENCE_MINUTES, build

TODAY = date(2026, 10, 9)


def _o(state: str, acc: float | None = None, n: int = 0) -> dict[str, object]:
    return {
        "outcome_id": uuid.uuid4(),
        "label": f"Topic {n}",
        "chapter_number": 1,
        "state": state,
        "independent_accuracy": acc,
    }


def test_feasible_plan_schedules_everything_weakest_first() -> None:
    outcomes = [
        _o("insufficient_evidence", n=1),
        _o("developing", 0.5, n=2),
        _o("demonstrated", n=3),
        _o("developing", 0.7, n=4),
    ]
    p = build(outcomes, today=TODAY, target=TODAY + timedelta(days=10), daily_minutes=60)
    assert p["feasible"] and p["shortfall_minutes"] == 0
    assert p["required_minutes"] == NO_EVIDENCE_MINUTES + 2 * DEVELOPING_MINUTES
    assert [x["label"] for x in p["schedule"]] == ["Topic 2", "Topic 4", "Topic 1"]  # low accuracy first


def test_infeasible_deadline_shows_the_shortfall_and_schedules_only_what_fits() -> None:
    outcomes = [_o("insufficient_evidence", n=i) for i in range(10)]
    p = build(outcomes, today=TODAY, target=TODAY + timedelta(days=2), daily_minutes=45)
    assert not p["feasible"] and p["shortfall_minutes"] == 10 * NO_EVIDENCE_MINUTES - 2 * 45
    assert len(p["schedule"]) == 2 and p["unscheduled_topics"] == 8
    assert all(x["date"] in (TODAY.isoformat(), (TODAY + timedelta(days=1)).isoformat()) for x in p["schedule"])


def test_the_endpoint_needs_daily_minutes_and_a_future_date(client: TestClient) -> None:
    from tests.test_attempts import _learner

    learner = _learner(client)
    q = {"grade": 11, "subject": "physics", "target_date": (date.today() + timedelta(days=30)).isoformat()}
    missing = client.get("/v1/me/study-plan", headers=learner.headers, params=q)
    assert missing.status_code == 422 and missing.json()["code_reason"] == "DAILY_MINUTES_NEEDED"
    ok = client.get("/v1/me/study-plan", headers=learner.headers, params={**q, "daily_minutes": 60})
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["rules_version"] == "evidence_rules_v2" and body["required_minutes"] > 0 and body["schedule"]
    past = {**q, "daily_minutes": 60, "target_date": (date.today() - timedelta(days=1)).isoformat()}
    assert client.get("/v1/me/study-plan", headers=learner.headers, params=past).status_code == 422


def test_without_evidence_the_plan_follows_the_book_order(client: TestClient) -> None:
    """Ties fall back to the book's chapter then topic order, never topic position across chapters."""
    from tests.test_attempts import _learner

    learner = _learner(client)
    ev = client.get("/v1/me/evidence", headers=learner.headers, params={"grade": 11, "subject": "biology"}).json()
    chapters = [o["chapter_number"] for o in ev["outcomes"]]
    assert len(set(chapters)) > 1 and chapters == sorted(chapters)
    q = {
        "grade": 11,
        "subject": "biology",
        "daily_minutes": 600,
        "target_date": (date.today() + timedelta(days=90)).isoformat(),
    }
    plan = client.get("/v1/me/study-plan", headers=learner.headers, params=q).json()
    scheduled = [x["chapter_number"] for x in plan["schedule"]]
    assert scheduled == sorted(scheduled)
