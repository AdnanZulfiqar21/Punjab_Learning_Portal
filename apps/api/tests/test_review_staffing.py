"""W06.S3.T2 (STAFFING-01): admission by staffing, overload behaviour and truthful turnaround.

Operators record the staffing behind a scope's capacity: productive reviewer hours a week, the fixed obligations taken
out of them, teacher minutes per script (the automatic route is disabled, so every script takes the full teacher
time) and the promised turnaround. New written starts are admitted only while the minutes left after fixed
obligations and the work already owed cover another script within the turnaround. Work already accepted continues,
learners see an honest turnaround, and nothing clears a backlog by approving answers. Fixture staff and scripts only.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.test_question_outcomes import _staff
from tests.test_written_attempts import _form, _learner, _map, _png, _seal, _start, _upload

URL = "/v1/ops/written-capacity/12/chemistry"


def _row(client: TestClient, operator: Any) -> dict[str, Any]:
    backlog = client.get("/v1/ops/written-backlog", headers=operator.headers).json()
    return dict(next(r for r in backlog if r["grade"] == 12 and r["subject"] == "chemistry"))


def _staffing(reviewer: int, fixed: int, minutes: int = 60, days: int = 7) -> dict[str, int]:
    return {
        "reviewer_hours_per_week": reviewer,
        "fixed_hours_per_week": fixed,
        "minutes_per_script": minutes,
        "turnaround_days": days,
    }


def test_staffing_admits_only_what_fits_after_fixed_and_owed_work(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    operator = _staff(client, ["platform_operator"], mfa=True)
    chapter = published_written["chapter"]
    load = _row(client, operator)["open_cases"] + _row(client, operator)["open_permits"]

    bad = {"max_open_cases": 10_000, "reason": "Fixture staffing", "staffing": _staffing(3, 4)}
    assert client.put(URL, headers=operator.headers, json=bad).status_code == 422  # fixed can't exceed productive
    partial = {"max_open_cases": 10_000, "reason": "Fixture staffing", "staffing": {"reviewer_hours_per_week": 5}}
    assert client.put(URL, headers=operator.headers, json=partial).status_code == 422  # all four or none

    try:
        # 60 minutes a script within a 7-day turnaround: (productive - fixed) hours admit that many scripts in total.
        # Fixed obligations come off first, then the work already owed, leaving room for exactly one more script.
        body = {"max_open_cases": 10_000, "reason": "Fixture: one script fits", "staffing": _staffing(load + 3, 2)}
        row = client.put(URL, headers=operator.headers, json=body).json()
        assert row["accepting"] and row["staffing"]["admissible_scripts"] == 1
        assert row["staffing"]["due_minutes"] == load * 60 and row["staffing"]["available_minutes"] == (load + 1) * 60

        first = _learner(client)
        started = _start(client, first, chapter)
        second = _learner(client)
        refused = client.post(
            f"/v1/written/forms/{_form(client, second, chapter).json()['id']}/attempt", headers=second.headers
        )
        assert refused.status_code == 409 and refused.json()["code_reason"] == "REVIEW_AT_CAPACITY"
        av = client.get("/v1/written/availability?grade=12&subject=chemistry", headers=second.headers).json()
        assert not av["review_accepting"]
        # Truthful turnaround: the owed work at today's productive minutes a day, rounded up.
        weekly = (load + 1) * 60
        assert av["turnaround_days"] == -(-((load + 1) * 60 + 60) * 7 // weekly)

        # Work already accepted continues: the started test can still be submitted and becomes a case.
        page = _upload(client, first, started["id"], _png(seed=77)).json()["pages"][0]["id"]
        m = _map(client, first, started, {"1:a": {"pages": [page]}, "1:b": {"unanswered": True}}).json()
        assert _seal(client, first, started["id"], m["manifest_revision"]).status_code == 200
        assert _row(client, operator)["open_cases"] >= 1

        # More fixed obligations leave less room: no new starts at all.
        tighter = {"max_open_cases": 10_000, "reason": "Fixture: training week", "staffing": _staffing(load + 3, 3)}
        assert client.put(URL, headers=operator.headers, json=tighter).json()["staffing"]["admissible_scripts"] == 0
    finally:
        restore = {"max_open_cases": 10_000, "reason": "Fixture: restore", "clear_staffing": True}
        row = client.put(URL, headers=operator.headers, json=restore).json()
        assert row["staffing"] is None and row["accepting"]
