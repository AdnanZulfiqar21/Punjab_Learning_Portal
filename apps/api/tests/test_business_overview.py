"""P16.S1.T1 (BUSINESS-OVERVIEW-01): aggregate business figures with definitions; test accounts kept out; purchases,
refunds and revenue unavailable until payments exist (B06). Fixture accounts only: the "real" learners here are rows
with a non-development issuer inserted purely as test setup."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from portal_api.modules.access.models import Entitlement, TrialGrant
from portal_api.modules.identity.models import AppUser
from tests.test_attempts import _learner
from tests.test_content_workflow import Staff

ISSUER = "https://idp.fixture.invalid/"


def _real_learner(trial_days_ago: int | None = None, seen_days_ago: int = 1) -> uuid.UUID:
    now = datetime.now(UTC)
    with get_sessionmaker()() as db:
        u = AppUser(
            id=uuid.uuid4(),
            issuer=ISSUER,
            subject=uuid.uuid4().hex,
            email=None,
            status="active",
            last_seen_at=now - timedelta(days=seen_days_ago),
        )
        db.add(u)
        db.flush()
        if trial_days_ago is not None:
            start = now - timedelta(days=trial_days_ago)
            e = Entitlement(
                id=uuid.uuid4(), user_id=u.id, source="trial", starts_at=start, ends_at=start + timedelta(days=30),
                status="active", reason="fixture trial",
            )  # fmt: skip
            db.add(e)
            db.flush()
            db.add(
                TrialGrant(
                    id=uuid.uuid4(), user_id=u.id, granted_at=start, ends_at=start + timedelta(days=30),
                    client="web", entitlement_id=e.id,
                )
            )  # fmt: skip
        db.commit()
        return u.id


def _overview(client: TestClient, who: Any) -> Any:
    return client.get("/v1/admin/business-overview", headers=who.headers)


def test_business_overview_counts_real_learners_only_and_admits_what_it_cannot_know(
    client: TestClient, db: Session
) -> None:
    admin, finance = Staff(client, db, ["owner_admin"], mfa=True), Staff(client, db, ["finance"], mfa=True)
    for who in (
        Staff(client, db, [], mfa=True),
        Staff(client, db, ["owner_admin"]),
        Staff(client, db, ["support"], mfa=True),
    ):
        assert _overview(client, who).status_code == 403
    before = _overview(client, admin).json()
    _real_learner(trial_days_ago=2)  # running trial, seen yesterday
    _real_learner(trial_days_ago=40, seen_days_ago=20)  # ended trial, seen 20 days ago
    _real_learner(seen_days_ago=60)  # no trial, inactive
    _learner(client)  # a development-adapter account with a trial: a test account
    after = _overview(client, finance).json()
    assert after["learners"] - before["learners"] == 3
    assert after["active_7d"] - before["active_7d"] == 1 and after["active_30d"] - before["active_30d"] == 2
    assert after["test_accounts"] > before["test_accounts"]
    assert after["entitlements_active"]["trial"] - before["entitlements_active"]["trial"] == 1
    for k in ("verified_purchases", "refunds", "revenue"):
        assert after[k]["available"] is False and after[k]["blocker"] == "B06"
    assert after["revenue"]["value"] is None
    weeks = {c["week_start"]: c for c in after["trial_cohorts"]}
    assert any(c["open"] and c["running"] >= 1 for c in weeks.values())
    assert all(c["ended"] == c["started"] - c["running"] for c in weeks.values())
    assert set(after["definitions"]) >= {"learners", "trial_cohorts", "verified_purchases", "content_usage_30d"}
    assert "email" not in str(after)
