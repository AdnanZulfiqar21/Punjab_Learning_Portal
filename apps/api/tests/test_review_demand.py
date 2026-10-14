"""W06.S3.T1 (DEMAND-01): measured review demand for a class and subject (roadmap §20.13.3).

* The recheck rate is rechecks over first markings released in the last 90 days, shown only once at least 20 were
  released; rechecks still expected are that rate times the first markings released in the 14-day recheck window.
* It is a forecast: admission is unchanged. What admission would be if expected rechecks were also subtracted is shown
  beside it, for the WA-D08 decision.
* Operators see it with the backlog.

Cases are inserted for a fixture-only scope against one real attempt, so no other test's work is counted.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from portal_api.db import get_sessionmaker
from portal_api.modules.written import review
from tests.test_question_outcomes import _staff
from tests.test_written_attempts import _learner, _start


def _cases(attempt_id: uuid.UUID, subject: str, rows: list[tuple[str, str, int]]) -> None:
    """(kind, status, days ago) per case, all in the fixture scope Class XI <subject>."""
    with get_sessionmaker()() as db:
        now = db.scalar(select(func.now()))
        assert now is not None
        seq = db.scalar(select(func.coalesce(func.max(review.WrittenReviewCase.opened_seq), 0))) or 0
        for kind, status, days in rows:
            seq += 1
            at = now - timedelta(days=days)
            db.add(
                review.WrittenReviewCase(
                    attempt_id=attempt_id,
                    case_kind=kind,
                    opened_seq=seq,
                    grade_number=11,
                    subject_code=subject,
                    status=status,
                    opened_at=at,
                    released_at=at if status == "released" else None,
                )
            )
        db.commit()


def test_recheck_demand_is_measured_only_from_enough_history_and_never_changes_admission(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    attempt = uuid.UUID(_start(client, _learner(client), published_written["chapter"])["id"])
    subject = f"fixture-demand-{uuid.uuid4().hex[:8]}"
    try:
        # 19 first markings released (10 of them within the recheck window), 2 rechecks, an old release outside 90 days.
        _cases(attempt, subject, [("initial", "released", 3)] * 10 + [("initial", "released", 40)] * 9)
        _cases(attempt, subject, [("recheck", "released", 5), ("recheck", "queued", 1), ("initial", "released", 120)])
        with get_sessionmaker()() as db:
            thin = review.review_demand(db, 11, subject, None)
        assert thin["released_scripts"] == 19 and thin["rechecks"] == 2
        assert thin["recheck_rate"] is None and thin["expected_rechecks"] == 0  # 19 isn't enough to call it a rate

        _cases(attempt, subject, [("initial", "released", 50), ("initial", "queued", 0), ("initial", "queued", 0)])
        with get_sessionmaker()() as db:
            db.add(
                review.ReviewCapacity(
                    grade_number=11,
                    subject_code=subject,
                    max_open_cases=100,
                    reason="Fixture: demand test",
                    reviewer_hours_per_week=10,
                    fixed_hours_per_week=0,
                    minutes_per_script=30,
                    turnaround_days=7,
                )
            )
            db.commit()
            cap = db.get(review.ReviewCapacity, (11, subject))
            measured = review.review_demand(db, 11, subject, cap)
            admission = review.capacity_state(db, 11, subject)
        assert measured["released_scripts"] == 20 and measured["recheck_rate"] == 0.1
        assert measured["recheck_window_releases"] == 10 and measured["expected_rechecks"] == 1  # ceil(0.1 x 10)
        assert measured["queued_by_kind"] == {"initial": 2, "recheck": 1, "completion": 0, "regrade": 0}
        assert measured["expected_recheck_minutes"] == 30
        # 600 minutes in the week; 3 queued cases owe 90; one expected recheck 30; each new script costs 30 x 1.1.
        assert measured["admissible_if_rechecks_counted"] == (600 - 90 - 30) * 10 // 330
        assert admission["staffing"]["admissible_scripts"] == (600 - 90) // 30  # admission itself is unchanged
    finally:
        with get_sessionmaker()() as db:
            db.execute(delete(review.WrittenReviewCase).where(review.WrittenReviewCase.subject_code == subject))
            db.execute(delete(review.ReviewCapacity).where(review.ReviewCapacity.subject_code == subject))
            db.commit()


def test_operators_see_demand_with_the_backlog(client: TestClient) -> None:
    operator = _staff(client, ["platform_operator"], mfa=True)
    rows = client.get("/v1/ops/written-backlog", headers=operator.headers).json()
    assert rows and all("demand" in r and "recheck_rate" in r["demand"] for r in rows)


def test_marking_time_is_measured_from_taking_a_script_to_releasing_it(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    # MARKING-TIME-01: the median over first markings with a recorded start, once ten were timed.
    attempt = uuid.UUID(_start(client, _learner(client), published_written["chapter"])["id"])
    subject = f"fixture-timing-{uuid.uuid4().hex[:8]}"
    try:
        with get_sessionmaker()() as db:
            now = db.scalar(select(func.now()))
            assert now is not None
            seq = db.scalar(select(func.coalesce(func.max(review.WrittenReviewCase.opened_seq), 0))) or 0
            for i, minutes in enumerate(range(10, 20)):  # 10..19 minutes: the median is 14.5
                released = now - timedelta(days=2, hours=i)
                db.add(
                    review.WrittenReviewCase(
                        attempt_id=attempt,
                        case_kind="initial",
                        opened_seq=seq + i + 1,
                        grade_number=11,
                        subject_code=subject,
                        status="released",
                        opened_at=released - timedelta(hours=5),
                        marking_started_at=released - timedelta(minutes=minutes),
                        released_at=released,
                    )
                )
                if i == 8:
                    db.commit()
                    nine = review.review_demand(db, 11, subject, None)
                    assert nine["timed_scripts"] == 9 and nine["median_take_to_release_minutes"] is None
            db.commit()
            ten = review.review_demand(db, 11, subject, None)
        assert ten["timed_scripts"] == 10 and ten["median_take_to_release_minutes"] == 14.5
    finally:
        with get_sessionmaker()() as db:
            db.execute(delete(review.WrittenReviewCase).where(review.WrittenReviewCase.subject_code == subject))
            db.commit()


def test_taking_a_case_records_when_marking_started_and_a_renewal_keeps_it(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    from tests.test_written_marking import _case_for, _reviewer, _sealed_script

    _, a = _sealed_script(client, published_written["chapter"])
    reviewer = _reviewer(client)
    case = _case_for(client, reviewer, a["id"])
    url = f"/v1/studio/written/cases/{case['id']}/lease"
    assert client.post(url, headers=reviewer.headers).status_code == 200

    def started() -> Any:
        with get_sessionmaker()() as db:
            c = db.get(review.WrittenReviewCase, uuid.UUID(case["id"]))
            assert c is not None
            return c.marking_started_at

    first = started()
    assert first is not None
    assert client.post(url, headers=reviewer.headers).status_code == 200  # renewing keeps the start
    assert started() == first
