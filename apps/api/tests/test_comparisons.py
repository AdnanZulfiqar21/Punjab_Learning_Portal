"""P12.S2.T3 (COMPARISON-01, AC62): a scheduled session's fixed form is compared honestly. One result per learner
account (200 retakes by one account count once), at least 200 accounts, midrank ties, a separate group for extra
time, and nothing shown while a correction is part-applied. Fixture profile and physics fixture questions; the other
learners are technical fixture rows inserted purely as test setup, and the development issuer is treated as a real
one for this module only (a separate fixture issuer stands in for test accounts)."""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from portal_api.modules.assessment import cohorts
from portal_api.modules.assessment.models import SCORING_POLICY_VERSION, Attempt, PracticeForm, ScoreVersion
from portal_api.modules.assessment.sessions import MockAccommodation, MockSession
from portal_api.modules.identity.models import AppUser, StaffRoleGrant
from tests.test_attempts import _form, _learner, _start
from tests.test_content_workflow import Staff
from tests.test_mock_sessions import _schedule, _shift
from tests.test_mocks import _publish_profile

FIXTURE_ISSUER = "https://idp.fixture.invalid/"
TECHNICAL = "urn:fixture:technical-accounts"


@pytest.fixture
def real_dev_accounts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cohorts, "_test_issuer", lambda: TECHNICAL)


def _submit(client: TestClient, who: Staff, attempt_id: str) -> None:
    r = client.post(
        f"/v1/attempts/{attempt_id}/submit", headers=who.headers, json={"idempotency_key": uuid.uuid4().hex, "ops": []}
    )
    assert r.status_code == 200, r.text


def _members(
    db: Session, session_id: str, raws: list[int], *, issuer: str = FIXTURE_ISSUER, **kw: Any
) -> list[uuid.UUID]:
    """Fixture accounts, each with one finalised attempt on a copy of the session's fixed form and one score."""
    s = db.get(MockSession, uuid.UUID(session_id))
    assert s is not None and s.master_form_id is not None
    users = []
    for raw in raws:
        u = AppUser(id=uuid.uuid4(), issuer=issuer, subject=uuid.uuid4().hex, status="active")
        db.add(u)
        db.flush()
        _attempt(db, s, u.id, raw, **kw)
        users.append(u.id)
    db.commit()
    return users


def _attempt(
    db: Session,
    s: MockSession,
    user_id: uuid.UUID,
    raw: int,
    *,
    status: str = "finalised",
    score: str = "scored",
    age: timedelta = timedelta(minutes=5),
    digest: str | None = None,
) -> uuid.UUID:
    master = db.get(PracticeForm, s.master_form_id)
    assert master is not None
    form = PracticeForm(
        id=uuid.uuid4(),
        owner_id=user_id,
        idempotency_key=f"fixture-{uuid.uuid4().hex}",
        request_hash="0" * 64,
        kind=master.kind,
        grade_number=master.grade_number,
        subject_code=master.subject_code,
        scope={**master.scope, "fixed_from": str(master.id)},
        seed=master.seed,
        question_count=master.question_count,
        duration_s=master.duration_s,
        late_write_tolerance_ms=master.late_write_tolerance_ms,
        feedback_mode=master.feedback_mode,
    )
    db.add(form)
    now = db.execute(select(func.clock_timestamp())).scalar_one()
    a = Attempt(
        id=uuid.uuid4(),
        form_id=form.id,
        user_id=user_id,
        status=status,
        started_at=now - age - timedelta(minutes=30),
        tolerance_ms=0,
        finalised_at=now - age,
        finalise_reason="manual",
    )
    db.add(a)
    db.flush()
    _score(db, a.id, raw, status=score, digest=digest or _digest(db, s))
    return a.id


def _digest(db: Session, s: MockSession) -> str:
    from portal_api.modules.assessment import scoring
    from portal_api.modules.assessment.adjudications import effective_for_form

    master = db.get(PracticeForm, s.master_form_id)
    assert master is not None
    return scoring.adjudication_hash(effective_for_form(db, master))


def _score(db: Session, attempt_id: uuid.UUID, raw: int, *, status: str = "scored", digest: str) -> None:
    prior = db.scalar(
        select(ScoreVersion).where(ScoreVersion.attempt_id == attempt_id).order_by(ScoreVersion.version.desc()).limit(1)
    )
    latest = prior.version if prior else 0
    db.add(
        ScoreVersion(
            attempt_id=attempt_id,
            version=latest + 1,
            scoring_policy_version=SCORING_POLICY_VERSION,
            adjudication_hash=digest,
            status=status,
            raw=raw,
            maximum=4,
            percentage=None,
            items=prior.items if prior else [],  # a revised score keeps the question rows
            reason="Fixture score",
        )
    )


def _build(session_id: str) -> list[Any]:
    with get_sessionmaker()() as s:
        sess = s.get(MockSession, uuid.UUID(session_id))
        assert sess is not None
        return [(x.timing_group, x.state, x.learners, x.version) for x in cohorts.build(s, sess)]


def _compared(client: TestClient, who: Staff, attempt_id: str) -> dict[str, Any]:
    r = client.get(f"/v1/attempts/{attempt_id}/result", headers=who.headers)
    assert r.status_code == 200, r.text
    return dict(r.json()["comparison"])


def test_a_fixed_session_is_compared_once_per_learner_with_midrank_ties(
    client: TestClient, db: Session, physics: dict[str, Any], real_dev_accounts: None
) -> None:
    code = _publish_profile(client, db, [{"subject": "physics", "grades": [11], "questions": 2}])
    admin = Staff(client, db, ["academic_adjudicator"], mfa=True)
    session = _schedule(client, admin, code)
    _shift(session["id"], starts_at=-10, entry_closes_at=5, window_closes_at=50, results_at=60)
    me = _learner(client)
    mine = client.post(f"/v1/mock-sessions/{session['id']}/join", headers=me.headers).json()["attempt_id"]
    _submit(client, me, mine)  # nothing answered: raw 0 of 4
    _shift(session["id"], results_at=-1)
    sid = uuid.UUID(session["id"])
    sess = db.get(MockSession, sid)
    assert sess is not None
    assert _compared(client, me, mine)["state"] == "pending"  # released, no snapshot yet: being prepared

    # One account with 200 retakes counts once (AC62): two accounts, far below the threshold.
    [retaker] = _members(db, session["id"], [4], age=timedelta(hours=2))
    for _ in range(199):  # later retakes, all scoring 0: only the first result (4) may count
        _attempt(db, sess, retaker, 0)
    db.commit()
    assert _build(session["id"]) == [("standard", "too_few", 2, 1)]
    shown = _compared(client, me, mine)
    assert shown["state"] == "too_few" and shown["percentile"] is None and shown["learners"] is None
    assert "fewer than 200 learners" in shown["message"]

    # Never members: a test account, a staff account, a void attempt, a result that couldn't be scored, one outside
    # the 90-day window; and extra time is compared only with extra time.
    _members(db, session["id"], [4], issuer=TECHNICAL)
    [staffer] = _members(db, session["id"], [4])
    db.add(StaffRoleGrant(user_id=staffer, role="academic_adjudicator", scope={}, reason="fixture"))
    _members(db, session["id"], [4], status="void")
    _members(db, session["id"], [0], score="not_scorable")
    _members(db, session["id"], [4], age=timedelta(days=91))
    [extra] = _members(db, session["id"], [0])
    db.add(MockAccommodation(session_id=sid, user_id=extra, extra_minutes=15, reason="Fixture", granted_by=admin.id))
    db.commit()
    # 198 more accounts: 50 level with me (raw 0) and 148 above (raw 4), so N = 200 with me and the retaker.
    _members(db, session["id"], [0] * 50 + [4] * 148)
    assert sorted(_build(session["id"])) == [("accommodated", "too_few", 1, 1), ("standard", "published", 200, 2)]
    assert _build(session["id"]) == []  # unchanged inputs make no new version

    shown = _compared(client, me, mine)
    # Lower 0, level 51 (me included): 100 * (0 + 25.5) / 200 = 12.75, shown to one decimal.
    assert shown["state"] == "published" and Decimal(str(shown["percentile"])) == Decimal("12.8")
    assert shown["learners"] == 200 and shown["version"] == 2 and shown["timing_group"] == "standard"
    assert shown["window_start"] and shown["window_end"] and "half" in shown["tie_rule"]
    assert "not proof of distinct people" in shown["limits"]

    # My score changes after the snapshot: no percentile from the old score.
    _score(db, uuid.UUID(mine), 2, digest="f" * 64)
    db.commit()
    assert _compared(client, me, mine)["message"].startswith("Your score changed after the comparison")
    # Rebuilt while that correction is part-applied (one score is on a newer set): hidden, never mixed.
    assert _build(session["id"]) == [("standard", "pending", 200, 3)]
    pending = _compared(client, me, mine)
    assert pending["state"] == "pending" and pending["percentile"] is None
    assert "never mixed" in pending["message"]


def test_varied_practice_and_test_accounts_are_not_compared(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    who = _learner(client)
    form = _form(client, who, physics["chapter"], count=2).json()
    attempt = _start(client, who, form["id"])
    _submit(client, who, attempt["id"])
    r = client.get(f"/v1/attempts/{attempt['id']}/result", headers=who.headers)
    assert r.status_code == 200 and r.json()["comparison"] is None  # practice forms are varied per learner

    code = _publish_profile(client, db, [{"subject": "physics", "grades": [11], "questions": 2}])
    session = _schedule(client, Staff(client, db, ["academic_adjudicator"], mfa=True), code)
    _shift(session["id"], starts_at=-10, entry_closes_at=5, window_closes_at=50, results_at=60)
    mine = client.post(f"/v1/mock-sessions/{session['id']}/join", headers=who.headers).json()["attempt_id"]
    _submit(client, who, mine)
    _shift(session["id"], results_at=-1)
    shown = _compared(client, who, mine)  # a development-issuer account, as every API-made account here is
    assert shown["state"] == "not_included" and "test accounts" in shown["message"]
