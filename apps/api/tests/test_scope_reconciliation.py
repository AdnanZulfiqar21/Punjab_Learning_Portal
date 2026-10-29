"""P19.S1.T2 (SCOPES-01): every assessment scope and correction rule, reconciled against the ledgers.

For topic, chapter, selected-chapter, half-book, full-book, combined 11+12 and full-mock tests, an independent check
from the database (not the screen) confirms the count, that every question comes from the scope and is published and
live, the timing and cutoff, that results wait for submission, and that the score equals the application's scoring
of the final-answer ledger with the receipt's ledger hash. The three correction treatments (EXCLUDE, CREDIT_ALL,
KEY_CORRECTION) and a zero denominator reconcile the same way. Questions and mappings are labelled technical
fixtures, not academic content.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from portal_api.modules.assessment import adjudications, attempts, forms, scoring
from portal_api.modules.assessment.forms import _book_chapters
from portal_api.modules.assessment.models import Attempt, FormItem, PracticeForm, SubmissionReceipt
from portal_api.modules.content.models import ContentItem
from portal_api.modules.curriculum.models import Topic
from tests.test_attempts import POOL, _learner, _op, _save_ops, publish_physics_pool
from tests.test_content_workflow import Staff, _post
from tests.test_mcq_corrections import _adjudicator, _correct, _keys
from tests.test_mocks import _mock, _publish_profile

CHAPTER_INDEX = 8  # this module's own pool; no other module uses it


@pytest.fixture(scope="module")
def pool(client: TestClient) -> dict[str, Any]:
    """This module quarantines and corrects questions, so it publishes its own pool in another chapter (OCT9-05)."""
    return publish_physics_pool(client, CHAPTER_INDEX)


def _form(client: TestClient, who: Staff, **body: Any) -> dict[str, Any]:
    r = client.post(
        "/v1/practice/forms",
        headers={**who.headers, "Idempotency-Key": uuid.uuid4().hex},
        json={"grade": 11, "subject": "physics", **body},
    )
    assert r.status_code == 201, r.text
    return dict(r.json())


def _finish(client: TestClient, who: Staff, form_id: str, *, wrong: frozenset[int] = frozenset()) -> str:
    started = client.post(f"/v1/practice/forms/{form_id}/attempt", headers=who.headers)
    assert started.status_code == 200, started.text
    a = started.json()
    assert client.get(f"/v1/attempts/{a['id']}/result", headers=who.headers).status_code == 409  # not released yet
    keys = _keys(form_id)
    ops = [
        _op(p, 1, k if p not in wrong else next(o for o in ("o1", "o2", "o3", "o4") if o != k)) for p, k in keys.items()
    ]
    assert _save_ops(client, who, a["id"], *ops).status_code == 200
    done = client.post(
        f"/v1/attempts/{a['id']}/submit", headers=who.headers, json={"idempotency_key": uuid.uuid4().hex, "ops": []}
    )
    assert done.status_code == 200, done.text
    return str(a["id"])


def _reconcile(attempt_id: str) -> dict[str, Any]:
    """Recompute the result from the ledgers and compare it with what was stored."""
    with get_sessionmaker()() as db:
        attempt = db.get(Attempt, uuid.UUID(attempt_id))
        assert attempt is not None and attempt.status == "finalised"
        form = db.get(PracticeForm, attempt.form_id)
        assert form is not None
        answers = attempts._answers(db, attempt)
        receipt = db.scalar(select(SubmissionReceipt).where(SubmissionReceipt.attempt_id == attempt.id))
        assert receipt is not None and receipt.ledger_hash == scoring.ledger_hash(answers)
        assert receipt.question_count == form.question_count == len(form.items)
        assert receipt.answered_count == sum(1 for o in answers.values() if o is not None)
        adjs = adjudications.effective_for_form(db, form)
        keys = forms.item_keys(db, form)
        expected = scoring.score(
            [
                scoring.ItemKey(
                    position=p, correct_option_id=k["correct_option_id"], option_ids=k["option_ids"], marks=k["marks"]
                )
                for p, k in keys.items()
            ],
            answers,
            negative_marks=form.negative_marks,
            adjudications=adjs,
        )
        sv = attempts.latest_score(db, attempt.id)
        assert sv is not None and sv.adjudication_hash == scoring.adjudication_hash(adjs)
        assert (sv.raw, sv.maximum, sv.status, sv.items) == (
            expected.raw,
            expected.maximum,
            expected.status,
            expected.items,
        )
        assert sv.raw == sum(i["earned"] for i in sv.items) and sv.maximum == sum(i["max"] for i in sv.items)
        if sv.maximum:
            assert float(sv.percentage) == round(100 * sv.raw / sv.maximum, 2)
        else:
            assert sv.percentage is None and sv.status == "not_scorable"
        return {"raw": sv.raw, "maximum": sv.maximum, "version": sv.version, "items": sv.items}


def _items(form_id: str) -> dict[int, str]:
    with get_sessionmaker()() as db:
        rows = db.execute(text("select position, item_id from form_item where form_id = :f"), {"f": form_id}).all()
        return {int(p): str(i) for p, i in rows}


def _disjoint(make: Any, taken: set[str]) -> dict[str, Any]:
    """Draw a new test until none of its questions is already used by another check (random draws can repeat)."""
    for _ in range(10):
        form = make()
        if not set(_items(form["id"]).values()) & taken:
            return dict(form)
    raise AssertionError("couldn't draw a test without the questions already in use")


def _drawn(form_id: str) -> list[tuple[uuid.UUID | None, uuid.UUID | None, str, bool, int]]:
    """For each frozen question: chapter, topic, availability, whether it's the published version, grade."""
    with get_sessionmaker()() as db:
        rows = db.execute(
            select(ContentItem.chapter_id, ContentItem.topic_id, ContentItem.availability, FormItem, ContentItem)
            .join(ContentItem, ContentItem.id == FormItem.item_id)
            .where(FormItem.form_id == uuid.UUID(form_id))
        ).all()
        return [(c, t, av, fi.version_id == item.published_version_id, fi.grade_number) for c, t, av, fi, item in rows]


def test_every_scope_draws_only_from_its_scope_and_reconciles(
    client: TestClient, db: Session, physics: dict[str, Any], pool: dict[str, Any]
) -> None:
    learner = _learner(client)
    xi = [c.id for c in _book_chapters(db, 11, "physics")]
    xii = [c.id for c in _book_chapters(db, 12, "physics")]
    mine = uuid.UUID(pool["chapter"])
    split = (len(xi) + 1) // 2
    half = 1 if xi.index(mine) < split else 2
    topic = db.scalar(select(Topic.id).where(Topic.chapter_id == mine, Topic.retired_at.is_(None)))
    assert topic is not None
    tagged = pool["ids"][:2]  # a technical topic mapping for two of this module's fixture questions
    db.execute(text("update content_item set topic_id = :t where id = any(:i)"), {"t": topic, "i": tagged})
    db.commit()

    cases: dict[str, tuple[dict[str, Any], set[uuid.UUID]]] = {
        "topic": ({"chapter_ids": [str(mine)], "topic_ids": [str(topic)], "question_count": 2}, {mine}),
        "chapter": ({"chapter_ids": [str(mine)], "question_count": POOL}, {mine}),
        "selected chapters": (
            {"chapter_ids": [str(mine), physics["chapter"]], "question_count": POOL + 2},
            {mine, uuid.UUID(physics["chapter"])},
        ),
        "half book": (
            {"scope": "half_book", "half": half, "question_count": 3},
            set(xi[:split] if half == 1 else xi[split:]),
        ),
        "full book": ({"scope": "full_book", "question_count": 4, "timed_minutes": 5}, set(xi)),
        "combined": ({"scope": "combined", "question_count": 4}, set(xi) | set(xii)),
    }
    for name, (body, allowed) in cases.items():
        form = _form(client, learner, **body)
        drawn = _drawn(form["id"])
        assert len(drawn) == body["question_count"], name
        assert all(c in allowed and av == "live" and published for c, _, av, published, _ in drawn), name
        if name == "topic":
            assert {t for _, t, *_ in drawn} == {topic}
        attempt_id = _finish(client, learner, form["id"], wrong=frozenset({1}))
        if body.get("timed_minutes"):
            with get_sessionmaker()() as s:
                a = s.get(Attempt, uuid.UUID(attempt_id))
                assert a is not None and a.deadline_at is not None and a.cutoff_at is not None
                assert a.deadline_at - a.started_at == timedelta(minutes=5)
                assert a.cutoff_at - a.deadline_at == timedelta(milliseconds=a.tolerance_ms)
        result = _reconcile(attempt_id)
        assert (result["raw"], result["maximum"]) == (body["question_count"] - 1, body["question_count"]), name

    # A full mock: every section's questions come from its subject and classes; the same reconciliation holds.
    code = _publish_profile(client, db, [{"subject": "physics", "grades": [11], "questions": 3}])
    mock = _mock(client, learner, code)
    assert mock.status_code == 201, mock.text
    drawn = _drawn(mock.json()["id"])
    assert len(drawn) == 3 and all(c in set(xi) and av == "live" and g == 11 for c, _, av, _, g in drawn)
    result = _reconcile(_finish(client, learner, mock.json()["id"], wrong=frozenset({2})))
    assert (result["raw"], result["maximum"]) == (2 * 2 - 1, 3 * 2)  # 2 marks each, 1 off for the wrong answer


def test_the_three_correction_treatments_and_a_zero_denominator_reconcile(
    client: TestClient, db: Session, physics: dict[str, Any], pool: dict[str, Any]
) -> None:
    learner, adjudicator, pub = _learner(client), _adjudicator(client), pool["publisher"]
    chapter = pool["chapter"]
    # Three tests whose questions don't overlap, so each correction lands on exactly one of them.
    one_form = _form(client, learner, chapter_ids=[chapter], question_count=1)
    single = _items(one_form["id"])[1]
    two_form = _disjoint(lambda: _form(client, learner, chapter_ids=[chapter], question_count=2), {single})
    key_position, rekeyed = 2, _items(two_form["id"])[2]
    code = _publish_profile(
        client, db, [{"subject": "physics", "grades": [11], "questions": 2}], invalid_item_treatment="CREDIT_ALL"
    )
    taken = {single, *_items(two_form["id"]).values()}
    mock = _disjoint(lambda: _mock(client, learner, code).json(), taken)
    mock_position = 1
    voided = {single, _items(mock["id"])[mock_position]}
    touched = voided | {rekeyed}
    one, two, mocked = (_finish(client, learner, f["id"]) for f in (one_form, two_form, mock))
    try:
        for item in voided:
            assert (
                _post(client, pub, item, "quarantine", {"reason": "Fixture: void", "level": "VOID"}).status_code == 200
            )
            assert (
                _correct(client, adjudicator, item, defect="VOID", reason="Fixture: no valid option").status_code == 201
            )
        key = _keys(two_form["id"])[key_position]
        other = next(o for o in ("o1", "o2", "o3", "o4") if o != key)
        quarantine = {"reason": "Fixture: wrong key", "level": "KEY_ERROR"}
        assert _post(client, pub, rekeyed, "quarantine", quarantine).status_code == 200
        corrected = _correct(
            client, adjudicator, rekeyed, defect="KEY_ERROR", corrected_option_id=other, reason="Fixture: key fixed"
        )
        assert corrected.status_code == 201, corrected.text

        zero = _reconcile(one)  # EXCLUDE on the only question: nothing left to score
        assert (zero["raw"], zero["maximum"], zero["version"]) == (0, 0, 2)
        assert zero["items"][0]["treatment"] == "EXCLUDE"
        key_fixed = _reconcile(two)  # KEY_CORRECTION: the published key is now wrong
        assert (key_fixed["raw"], key_fixed["maximum"], key_fixed["version"]) == (1, 2, 2)
        assert key_fixed["items"][key_position - 1]["treatment"] == "KEY_CORRECTION"
        credited = _reconcile(mocked)  # CREDIT_ALL, pinned by the mock's pattern
        assert credited["items"][mock_position - 1]["treatment"] == "CREDIT_ALL" and credited["version"] == 2
        assert (credited["raw"], credited["maximum"]) == (4, 4)
    finally:
        with get_sessionmaker()() as s:
            s.execute(
                text("update mcq_adjudication set status = 'superseded' where item_id = any(:i)"), {"i": list(touched)}
            )
            s.commit()
        for item in touched:
            _post(client, pub, item, "release", {"reason": "Fixture cleanup"})
