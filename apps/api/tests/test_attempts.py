"""Practice forms and the §10.5 attempt protocol (P09/P10). Questions are technical fixtures published inside this test
database only (rights confirmed here for the fixture source); nothing here is academic content."""

from __future__ import annotations

import copy
import threading
import uuid
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from portal_api.errors import AttemptFinalised
from portal_api.modules.assessment import attempts, scoring
from portal_api.modules.assessment.models import Attempt, SubmissionReceipt
from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _post, _refs
from tests.test_mcq_items import CHECKS, VALID, _new_mcq, _save

POOL = 6


@pytest.fixture(scope="module")
def physics(client: TestClient) -> dict[str, Any]:
    """Publish POOL fixture questions in one Class XI Physics chapter (keys rotate o1..o4)."""
    with get_sessionmaker()() as db:
        scope = {"grades": [11], "subjects": ["physics"]}
        author = Staff(client, db, ["content_author"], scope)
        reviewer = Staff(client, db, ["subject_reviewer"], scope)
        publisher = Staff(client, db, ["publisher"], scope, mfa=True)
        chapter, doc = _chapter(db, 11, "physics")
        _confirm_rights(client, db, doc)
        keys: dict[str, str] = {}
        ids = []
        for i in range(POOL):
            item = _new_mcq(client, author, str(chapter.id))
            body = copy.deepcopy(VALID)
            key = f"o{i % 4 + 1}"
            body["correct_option_id"] = key
            body["explanation"]["distractors"] = {}
            body["stem"] = [{"type": "paragraph", "text": f"Fixture stem {i}"}]
            assert _save(client, author, item, body, _refs(chapter, doc)).status_code == 200
            assert _post(client, author, item["id"], "submit").status_code == 200
            ok = _post(
                client,
                reviewer,
                item["id"],
                "review",
                {"decision": "approve", "comment": "Fixture check", "checklist": CHECKS},
            )
            assert ok.status_code == 200, ok.text
            assert _post(client, publisher, item["id"], "publish").status_code == 200
            keys[item["id"]] = key
            ids.append(item["id"])
        return {"chapter": str(chapter.id), "keys": keys, "ids": ids, "publisher": publisher, "author": author}


def _learner(client: TestClient) -> Staff:
    with get_sessionmaker()() as db:
        return Staff(client, db, [])


def _form(client: TestClient, who: Staff, chapter: str, count: int = 4, key: str | None = None, **extra: Any) -> Any:
    return client.post(
        "/v1/practice/forms",
        headers={**who.headers, "Idempotency-Key": key or uuid.uuid4().hex},
        json={"grade": 11, "subject": "physics", "chapter_ids": [chapter], "question_count": count, **extra},
    )


def _start(client: TestClient, who: Staff, form_id: str) -> dict[str, Any]:
    r = client.post(f"/v1/practice/forms/{form_id}/attempt", headers=who.headers)
    assert r.status_code == 200, r.text
    return dict(r.json())


def _op(position: int, revision: int, option: str | None, op_id: str | None = None) -> dict[str, Any]:
    return {"op_id": op_id or str(uuid.uuid4()), "position": position, "revision": revision, "option_id": option}


def _save_ops(client: TestClient, who: Staff, attempt_id: str, *ops: dict[str, Any]) -> Any:
    return client.post(f"/v1/attempts/{attempt_id}/answers", headers=who.headers, json={"ops": list(ops)})


def _set_times(attempt_id: str, *, deadline_offset_s: float, cutoff_offset_s: float) -> None:
    with get_sessionmaker()() as db:
        db.execute(
            text(
                "update attempt set deadline_at = clock_timestamp() + make_interval(secs => :d), "
                "cutoff_at = clock_timestamp() + make_interval(secs => :c) where id = :id"
            ),
            {"d": deadline_offset_s, "c": cutoff_offset_s, "id": attempt_id},
        )
        db.commit()


# ------------------------------------------------------------------ scoring (pure)
def test_scoring_rules() -> None:
    keys = [scoring.ItemKey(p, "a", ("a", "b", "c"), 1) for p in (1, 2, 3)]
    r = scoring.score(keys, {1: "a", 2: "b", 3: None})
    assert (r.raw, r.maximum, r.percentage) == (1, 3, Decimal("33.33"))
    assert [i["correct"] for i in r.items] == [True, False, False]
    neg = scoring.score(keys, {1: "a", 2: "b"}, negative_marks=1)
    assert (neg.raw, neg.maximum) == (0, 3)  # +1 then -1, blank 0
    two_thirds = scoring.score(keys, {1: "a", 2: "a"})
    assert two_thirds.percentage == Decimal("66.67")  # half-up rounding
    adj = [
        scoring.Adjudication(1, "EXCLUDE"),
        scoring.Adjudication(2, "CREDIT_ALL"),
        scoring.Adjudication(3, "KEY_CORRECTION", "c"),
    ]
    corrected = scoring.score(keys, {1: "a", 2: None, 3: "c"}, adjudications=adj)
    assert (corrected.raw, corrected.maximum) == (2, 2)
    void_all = scoring.score(keys, {1: "a"}, adjudications=[scoring.Adjudication(p, "EXCLUDE") for p in (1, 2, 3)])
    assert void_all.status == "not_scorable" and void_all.percentage is None
    assert scoring.adjudication_hash(adj) == scoring.adjudication_hash(list(reversed(adj)))


# ------------------------------------------------------------------ forms
def test_availability_and_honest_pool_shortage(client: TestClient, physics: dict[str, Any]) -> None:
    who = _learner(client)
    av = client.get("/v1/practice/availability?grade=11&subject=physics", headers=who.headers).json()
    row = next(c for c in av["chapters"] if c["chapter_id"] == physics["chapter"])
    assert row["questions"] == POOL
    short = _form(client, who, physics["chapter"], count=POOL + 1)
    assert short.status_code == 422 and short.json()["available"] == POOL and short.json()["requested"] == POOL + 1


def test_forms_are_frozen_idempotent_and_exclude_quarantined(client: TestClient, physics: dict[str, Any]) -> None:
    who = _learner(client)
    key = uuid.uuid4().hex
    first = _form(client, who, physics["chapter"], count=4, key=key)
    assert first.status_code == 201, first.text
    again = _form(client, who, physics["chapter"], count=4, key=key)
    assert again.json()["id"] == first.json()["id"]
    changed = _form(client, who, physics["chapter"], count=3, key=key)
    assert changed.status_code == 409
    # Quarantined questions leave the pool for new forms.
    pub = physics["publisher"]
    q = _post(client, pub, physics["ids"][0], "quarantine", {"reason": "Fixture suspected defect", "level": "SOFT"})
    assert q.status_code == 200
    try:
        assert _form(client, who, physics["chapter"], count=POOL).status_code == 422
        assert _form(client, who, physics["chapter"], count=POOL - 1).status_code == 201
    finally:
        _post(client, pub, physics["ids"][0], "release", {"reason": "Fixture defect not confirmed"})


def test_attempt_payload_never_contains_keys(client: TestClient, physics: dict[str, Any]) -> None:
    who = _learner(client)
    form = _form(client, who, physics["chapter"], count=POOL).json()
    attempt = _start(client, who, form["id"])
    raw = str(attempt)
    for secret in ("correct_option_id", "explanation", "distractors"):
        assert secret not in raw
    assert len(attempt["items"]) == POOL and attempt["status"] == "active" and attempt["deadline_at"] is None
    assert all(len(i["options"]) == 4 for i in attempt["items"])
    # Starting again resumes the same attempt.
    assert _start(client, who, form["id"])["id"] == attempt["id"]


# ------------------------------------------------------------------ saves
def test_save_dispositions(client: TestClient, physics: dict[str, Any]) -> None:
    who = _learner(client)
    a = _start(client, who, _form(client, who, physics["chapter"]).json()["id"])
    opt = a["items"][0]["options"][0]["id"]
    first = _op(1, 1, opt)
    r = _save_ops(client, who, a["id"], first).json()["results"][0]
    assert r["disposition"] == "accepted" and not r["replay"]
    replay = _save_ops(client, who, a["id"], first).json()["results"][0]
    assert replay["disposition"] == "accepted" and replay["replay"] and replay["admitted_at"] == r["admitted_at"]
    reused = _save_ops(client, who, a["id"], {**first, "option_id": None}).json()["results"][0]
    assert reused["disposition"] == "conflict"
    stale = _save_ops(client, who, a["id"], _op(1, 1, a["items"][0]["options"][1]["id"])).json()["results"][0]
    assert stale["disposition"] == "stale"
    batch = _save_ops(client, who, a["id"], _op(1, 3, None), _op(2, 1, "zz"), _op(99, 1, opt)).json()["results"]
    assert [x["disposition"] for x in batch] == ["accepted", "invalid", "invalid"]
    resumed = client.get(f"/v1/attempts/{a['id']}", headers=who.headers).json()
    assert resumed["answers"] == [
        {**resumed["answers"][0], "position": 1, "option_id": None, "revision": 3}
    ]  # cleared at revision 3; newer revisions win, older ones never overwrite


def test_other_people_cannot_see_or_change_an_attempt(client: TestClient, physics: dict[str, Any]) -> None:
    owner, other = _learner(client), _learner(client)
    form = _form(client, owner, physics["chapter"]).json()
    a = _start(client, owner, form["id"])
    assert client.get(f"/v1/attempts/{a['id']}", headers=other.headers).status_code == 404
    assert client.post(f"/v1/practice/forms/{form['id']}/attempt", headers=other.headers).status_code == 404
    assert _save_ops(client, other, a["id"], _op(1, 1, "o1")).status_code == 404


# ------------------------------------------------------------------ submission
def test_manual_submit_is_atomic_idempotent_and_final(client: TestClient, physics: dict[str, Any]) -> None:
    who = _learner(client)
    form = _form(client, who, physics["chapter"], count=POOL).json()
    a = _start(client, who, form["id"])
    saved = _op(1, 1, a["items"][0]["options"][0]["id"])
    _save_ops(client, who, a["id"], saved)
    last_click = _op(2, 1, a["items"][1]["options"][1]["id"])  # the debounced last click travels with submit
    key = uuid.uuid4().hex
    s1 = client.post(
        f"/v1/attempts/{a['id']}/submit", headers=who.headers, json={"idempotency_key": key, "ops": [last_click]}
    )
    assert s1.status_code == 200, s1.text
    receipt = s1.json()["receipt"]
    assert receipt["reason"] == "manual" and receipt["answered_count"] == 2 and receipt["question_count"] == POOL
    s2 = client.post(
        f"/v1/attempts/{a['id']}/submit", headers=who.headers, json={"idempotency_key": key, "ops": [last_click]}
    )
    assert s2.json()["receipt"] == receipt and s2.json()["same_request"]
    unsent = _op(3, 1, a["items"][2]["options"][0]["id"])
    s3 = client.post(
        f"/v1/attempts/{a['id']}/submit",
        headers=who.headers,
        json={"idempotency_key": uuid.uuid4().hex, "ops": [unsent]},
    )
    assert s3.json()["receipt"] == receipt and not s3.json()["same_request"]
    assert s3.json()["reconciliation"][0]["disposition"] == "finalised"  # reported separately; receipt unchanged
    late_save = _save_ops(client, who, a["id"], _op(4, 1, a["items"][3]["options"][0]["id"]))
    assert late_save.status_code == 409 and late_save.json()["title"] == "ATTEMPT_FINALISED"
    assert late_save.json()["receipt_id"] == receipt["id"]
    replay = _save_ops(client, who, a["id"], saved)  # an exact replay of a committed op still gets its receipt
    assert replay.status_code == 200 and replay.json()["results"][0]["disposition"] == "accepted"

    result = client.get(f"/v1/attempts/{a['id']}/result", headers=who.headers).json()
    keys = physics["keys"]
    item_ids = _form_item_ids(form["id"])
    expected = sum(
        1 for pos, chosen in ((1, saved["option_id"]), (2, last_click["option_id"])) if keys[item_ids[pos]] == chosen
    )
    assert result["raw"] == expected and result["maximum"] == POOL and result["answered"] == 2
    assert all("correct_option_id" in i and "explanation" in i for i in result["items"])  # released after submit


def _form_item_ids(form_id: str) -> dict[int, str]:
    with get_sessionmaker()() as db:
        rows = db.execute(text("select position, item_id from form_item where form_id = :f"), {"f": form_id}).all()
        return {int(p): str(i) for p, i in rows}


def test_results_wait_for_submission(client: TestClient, physics: dict[str, Any]) -> None:
    who = _learner(client)
    a = _start(client, who, _form(client, who, physics["chapter"]).json()["id"])
    assert client.get(f"/v1/attempts/{a['id']}/result", headers=who.headers).status_code == 409


# ------------------------------------------------------------------ deadlines
def test_deadline_tolerance_and_late_writes(client: TestClient, physics: dict[str, Any]) -> None:
    who = _learner(client)
    form = _form(client, who, physics["chapter"], timed_minutes=10).json()
    assert form["late_write_tolerance_ms"] == 3000 and form["duration_s"] == 600
    a = _start(client, who, form["id"])
    assert a["deadline_at"] and a["cutoff_at"] and a["tolerance_ms"] == 3000
    # Past D but inside the tolerance window: admitted.
    _set_times(a["id"], deadline_offset_s=-1, cutoff_offset_s=2)
    inside = _save_ops(client, who, a["id"], _op(1, 1, a["items"][0]["options"][0]["id"])).json()
    assert inside["results"][0]["disposition"] == "accepted"
    # After C: late, and the attempt is finalised by expiry under the same lock with the committed answer.
    _set_times(a["id"], deadline_offset_s=-5, cutoff_offset_s=-0.001)
    after = _save_ops(client, who, a["id"], _op(2, 1, a["items"][1]["options"][0]["id"]))
    assert after.status_code == 200
    assert after.json()["results"][0]["disposition"] == "late" and after.json()["status"] == "finalised"
    resumed = client.get(f"/v1/attempts/{a['id']}", headers=who.headers).json()
    assert resumed["receipt"]["reason"] == "expiry" and resumed["receipt"]["answered_count"] == 1


def test_manual_submit_after_cutoff_cannot_add_answers(client: TestClient, physics: dict[str, Any]) -> None:
    who = _learner(client)
    a = _start(client, who, _form(client, who, physics["chapter"], timed_minutes=5).json()["id"])
    _set_times(a["id"], deadline_offset_s=-10, cutoff_offset_s=-7)
    r = client.post(
        f"/v1/attempts/{a['id']}/submit",
        headers=who.headers,
        json={"idempotency_key": uuid.uuid4().hex, "ops": [_op(1, 1, a["items"][0]["options"][0]["id"])]},
    ).json()
    assert r["receipt"]["reason"] == "expiry" and r["receipt"]["answered_count"] == 0


def test_expiry_worker_finalises_due_attempts(client: TestClient, physics: dict[str, Any], db: Session) -> None:
    who = _learner(client)
    a = _start(client, who, _form(client, who, physics["chapter"], timed_minutes=5).json()["id"])
    _save_ops(client, who, a["id"], _op(1, 1, a["items"][0]["options"][0]["id"]))
    _set_times(a["id"], deadline_offset_s=-3, cutoff_offset_s=-1)
    assert attempts.expire_due(db) >= 1
    row = db.get(Attempt, uuid.UUID(a["id"]))
    assert row is not None and row.status == "finalised" and row.finalise_reason == "expiry"
    receipt = db.scalar(select(SubmissionReceipt).where(SubmissionReceipt.attempt_id == row.id))
    assert receipt is not None and receipt.answered_count == 1
    db.expire_all()
    assert attempts.expire_due(db) == 0 or db.get(Attempt, row.id).status == "finalised"  # type: ignore[union-attr]


# ------------------------------------------------------------------ serialisation
def _race(who: Any, attempt_id: uuid.UUID, op: attempts.Op) -> dict[str, Any]:
    """Start a save and a submit for one attempt at the same instant; return what each observed."""
    barrier = threading.Barrier(2)
    out: dict[str, Any] = {}

    def do_save() -> None:
        with get_sessionmaker()() as s:
            barrier.wait()
            try:
                out["save"] = attempts.save(s, who, attempt_id, [op])["results"][0]["disposition"]
            except AttemptFinalised:
                out["save"] = "finalised"

    def do_submit() -> None:
        with get_sessionmaker()() as s:
            barrier.wait()
            out["receipt"] = attempts.submit(s, who, attempt_id, uuid.uuid4().hex, [])["receipt"].answered_count

    threads = [threading.Thread(target=do_save), threading.Thread(target=do_submit)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return out


def test_concurrent_save_and_submit_never_lose_an_acknowledged_answer(
    client: TestClient, physics: dict[str, Any]
) -> None:
    """Race a save against a submit many times. The row lock serialises them: an acknowledged (accepted) save is always
    in the receipt's ledger, and a save that lost the race is reported as finalised, never silently dropped."""
    learner = _learner(client)
    who = SimpleNamespace(user=SimpleNamespace(id=learner.id))
    outcomes = set()
    for _ in range(8):
        a = _start(client, learner, _form(client, learner, physics["chapter"]).json()["id"])
        op = attempts.Op(op_id=uuid.uuid4(), position=1, revision=1, option_id=a["items"][0]["options"][0]["id"])
        out = _race(who, uuid.UUID(a["id"]), op)
        assert out["save"] in ("accepted", "finalised")
        assert out["receipt"] == (1 if out["save"] == "accepted" else 0)
        outcomes.add(out["save"])
    assert outcomes  # at least one ordering observed; both orderings are valid


# ------------------------------------------------------------------ immediate feedback
def test_immediate_feedback_locks_the_checked_item(client: TestClient, physics: dict[str, Any]) -> None:
    who = _learner(client)
    a = _start(client, who, _form(client, who, physics["chapter"], feedback_mode="immediate").json()["id"])
    first = a["items"][0]["options"][0]["id"]
    assert client.post(f"/v1/attempts/{a['id']}/items/1/reveal", headers=who.headers).status_code == 422  # unanswered
    _save_ops(client, who, a["id"], _op(1, 1, first))
    rev = client.post(f"/v1/attempts/{a['id']}/items/1/reveal", headers=who.headers)
    assert rev.status_code == 200 and rev.json()["chosen"] == first and "explanation" in rev.json()
    locked = _save_ops(client, who, a["id"], _op(1, 2, a["items"][0]["options"][1]["id"])).json()["results"][0]
    assert locked["disposition"] == "locked"
    deferred = _start(client, who, _form(client, who, physics["chapter"]).json()["id"])
    _save_ops(client, who, deferred["id"], _op(1, 1, deferred["items"][0]["options"][0]["id"]))
    assert client.post(f"/v1/attempts/{deferred['id']}/items/1/reveal", headers=who.headers).status_code == 409


def test_finalised_attempt_rejects_unknown_ops_with_receipt(client: TestClient, physics: dict[str, Any]) -> None:
    who = _learner(client)
    a = _start(client, who, _form(client, who, physics["chapter"]).json()["id"])
    client.post(f"/v1/attempts/{a['id']}/submit", headers=who.headers, json={"idempotency_key": uuid.uuid4().hex})
    r = _save_ops(client, who, a["id"], _op(1, 1, a["items"][0]["options"][0]["id"]))
    assert r.status_code == 409 and r.json()["results"][0]["disposition"] == "finalised"
