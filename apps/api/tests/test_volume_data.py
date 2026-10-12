"""P20.S1.T1 (VOLUME-01): generated load histories have the shapes the application writes and reads.

A small run in the test database (allowed by name) must produce rows that the application's own scoring, ledger
hash, progress report and dashboard accept unchanged, use only published questions, count as test accounts, and
respect the budgets. Technical fixtures only; nothing here is academic content.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import func, select, text

from loadtest import volume
from portal_api.config import get_settings
from portal_api.db import get_engine, get_sessionmaker
from portal_api.modules.assessment import attempts, dashboard, forms, progress, scoring
from portal_api.modules.assessment.models import Attempt, PracticeForm, ScoreVersion, SubmissionReceipt
from portal_api.modules.identity.models import AppUser


def test_a_small_run_matches_what_the_application_computes(physics: dict[str, Any]) -> None:
    engine = get_engine()
    run = uuid.uuid4().hex[:8]
    plan = volume.Plan(accounts=3, attempts=2, questions=4, revisions=2, grade=11, subject="physics", run=run)
    report = volume.generate(engine, plan, allow_database=str(engine.url.database))
    assert (report.accounts, report.attempts, report.answer_revisions) == (3, 6, 48)
    assert 4 <= report.distinct_questions_used <= report.distinct_questions_available
    assert "B06" in report.purchase_events and "none claimed" in report.academic_coverage

    with get_sessionmaker()() as db:
        users = list(db.scalars(select(AppUser).where(AppUser.subject.like(f"load-{run}-%"))))
        assert len(users) == 3 and {u.issuer for u in users} == {get_settings().dev_auth_issuer}  # test accounts
        ids = [u.id for u in users]
        tries = list(db.scalars(select(Attempt).where(Attempt.user_id.in_(ids))))
        assert len(tries) == 6 and {a.status for a in tries} == {"finalised"}
        ops = db.scalar(
            select(func.count()).select_from(text("answer_op")).where(text("attempt_id = any(:a)")),
            {"a": [a.id for a in tries]},
        )
        assert ops == 48
        for a in tries:
            form = db.get(PracticeForm, a.form_id)
            assert form is not None and form.question_count == 4
            answers = attempts._answers(db, a)
            receipt = db.scalar(select(SubmissionReceipt).where(SubmissionReceipt.attempt_id == a.id))
            assert receipt is not None and receipt.ledger_hash == scoring.ledger_hash(answers)
            keys = forms.item_keys(db, form)
            expected = scoring.score(
                [
                    scoring.ItemKey(
                        position=p,
                        correct_option_id=k["correct_option_id"],
                        option_ids=k["option_ids"],
                        marks=k["marks"],
                    )
                    for p, k in keys.items()
                ],
                answers,
                negative_marks=form.negative_marks,
                adjudications=[],
            )
            sv = attempts.latest_score(db, a.id)
            assert isinstance(sv, ScoreVersion)
            assert (sv.raw, sv.maximum, sv.status) == (expected.raw, expected.maximum, expected.status)
            assert sv.items == expected.items
            assert sv.adjudication_hash == scoring.adjudication_hash([])
        # The learner-facing reports read the generated histories as they are.
        report_one = progress.report(db, ids[0])
        row = next(s for s in report_one["subjects"] if (s["grade"], s["subject"]) == (11, "physics"))
        assert row["tests"] == 2 and row["questions_answered"] == 8
        assert len(dashboard.build(db, ids[0])["recent"]) == 2
        db.rollback()


def test_runs_stay_within_budget_and_dedicated_databases() -> None:
    too_many = volume.Plan(accounts=100_001, attempts=1, questions=1, revisions=1, grade=11, subject="physics", run="x")
    too_much = volume.Plan(
        accounts=100_000, attempts=10, questions=10, revisions=2, grade=11, subject="physics", run="x"
    )
    for plan in (too_many, too_much):
        with pytest.raises(volume.Refused):
            volume.check_plan(plan)
    with pytest.raises(volume.Refused, match="dedicated load database"):
        volume.check_target(get_engine(), allow_database=None)  # the test database's name doesn't end in _load
    assert (
        volume.main(["--database-url", str(get_engine().url.render_as_string(hide_password=False)), "--accounts", "1"])
        == 2
    )
