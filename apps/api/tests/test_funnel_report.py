"""P16.S2.T2 (FUNNEL-01): funnel and repeat study by sign-up cohort from analytics events; young cohorts are
"too early", not drop-off; paid conversion unavailable until payments (B06). Fixture accounts and events are inserted
as test setup."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from portal_api.modules.analytics.events import emit
from portal_api.modules.identity.models import AppUser
from tests.test_content_workflow import Staff

ISSUER = "https://idp.fixture.invalid/"


def _learner_with(created: datetime, activity: list[tuple[str, int]]) -> None:
    """A non-test account created at `created`, with (event, days after creation) activity."""
    with get_sessionmaker()() as db:
        u = AppUser(id=uuid.uuid4(), issuer=ISSUER, subject=uuid.uuid4().hex, status="active", created_at=created)
        db.add(u)
        db.flush()
        for name, day in activity:
            props: dict[str, Any] = (
                {"lesson_id": str(uuid.uuid4()), "language": "en"}
                if name == "lesson.started"
                else {"attempt_id": str(uuid.uuid4()), "reason": "manual", "answered": 1, "question_count": 1}
            )
            emit(db, name, key=f"{u.id}:{name}:{day}", user_id=u.id, at=created + timedelta(days=day, hours=1), **props)
        db.commit()


def _cohort(report: dict[str, Any], start: datetime) -> dict[str, Any]:
    monday = (start - timedelta(days=start.weekday())).date().isoformat()
    return next((c for c in report["cohorts"] if c["week_start"] == monday), {"signed_up": 0})


def test_funnel_counts_each_step_once_and_respects_cohort_age(client: TestClient, db: Session) -> None:
    viewer = Staff(client, db, ["owner_admin"], mfa=True)
    url = "/v1/admin/analytics/funnel"
    assert client.get(url, headers=Staff(client, db, ["owner_admin"]).headers).status_code == 403  # MFA
    old = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(weeks=9)
    old = old - timedelta(days=old.weekday())  # a Monday, so every day below stays in one cohort week
    _learner_with(old, [("lesson.started", 0), ("attempt.submitted", 5)])  # repeat study within 14 days
    _learner_with(old, [("lesson.started", 0), ("lesson.started", 20)])  # second day too late: no repeat
    _learner_with(old, [])  # signed up, nothing else
    r = client.get(url, headers=viewer.headers)
    assert r.status_code == 200, r.text
    c = _cohort(r.json(), old)
    assert (c["signed_up"], c["first_lesson"], c["first_completed_test"], c["repeat_study"]) == (3, 2, 1, 1)
    assert c["repeat_study_too_early"] is False and c["age_days"] >= 63
    assert c["paid_conversion"] == {"value": None, "available": False, "blocker": "B06"}

    now = datetime.now(UTC)
    before = _cohort(client.get(url, headers=viewer.headers).json(), now)
    _learner_with(now - timedelta(minutes=1), [("lesson.started", 0)])
    after = _cohort(client.get(url, headers=viewer.headers).json(), now)
    assert after["signed_up"] - before["signed_up"] == 1 and after["first_lesson"] - before.get("first_lesson", 0) == 1
    assert after["repeat_study_too_early"] is True  # a week-old cohort can't have shown repeat study yet
    report = client.get(url, headers=viewer.headers).json()
    assert report["events_since"] is not None and "coverage" in report["definitions"]
