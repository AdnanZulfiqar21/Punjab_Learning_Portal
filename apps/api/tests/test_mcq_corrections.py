"""§5.7 / P10.S3.T4: reviewed VOID and KEY_ERROR corrections re-score affected attempts as new score versions from the
immutable ledger, idempotently, with the learner told once per new version. Includes the disputed-question incident
rehearsal (P15.S4.T3, `docs/runbooks/disputed-question.md`). Questions are technical fixtures."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from portal_api.db import get_sessionmaker
from portal_api.modules.assessment import adjudications
from portal_api.modules.assessment.models import ScoreVersion
from tests import test_attempts
from tests.test_attempts import POOL, _form, _form_item_ids, _learner, _op, _save_ops, _start
from tests.test_content_workflow import Staff, _post

SCOPE = {"grades": [11], "subjects": ["physics"]}


@pytest.fixture(scope="module")
def physics(client: TestClient) -> dict[str, Any]:
    """This module changes question versions, so it publishes its own pool in another chapter (OCT9-05)."""
    return test_attempts.publish_physics_pool(client, 1)


def _adjudicator(client: TestClient, mfa: bool = True) -> Staff:
    with get_sessionmaker()() as db:
        return Staff(client, db, ["academic_adjudicator"], SCOPE, mfa=mfa)


def _keys(form_id: str) -> dict[int, str]:
    """The published key at each position of a frozen form (the chapter pool is shared with other test modules)."""
    with get_sessionmaker()() as db:
        rows = db.execute(
            text(
                "select fi.position, v.body->>'correct_option_id' from form_item fi "
                "join content_version v on v.id = fi.version_id where fi.form_id = :f"
            ),
            {"f": form_id},
        ).all()
        return {int(p): str(k) for p, k in rows}


def _finish_all_correct(
    client: TestClient, who: Staff, physics: dict[str, Any]
) -> tuple[dict[str, Any], dict[int, str]]:
    """Answer every question with its published key and submit."""
    form = _form(client, who, physics["chapter"], count=POOL).json()
    a = _start(client, who, form["id"])
    item_ids = _form_item_ids(form["id"])
    keys = _keys(form["id"])
    ops = [_op(p, 1, keys[p]) for p in sorted(item_ids)]
    assert _save_ops(client, who, a["id"], *ops).status_code == 200
    r = client.post(
        f"/v1/attempts/{a['id']}/submit", headers=who.headers, json={"idempotency_key": uuid.uuid4().hex, "ops": []}
    )
    assert r.status_code == 200, r.text
    return {**a, "form_id": form["id"]}, item_ids


def _result(client: TestClient, who: Staff, attempt_id: str) -> dict[str, Any]:
    r = client.get(f"/v1/attempts/{attempt_id}/result", headers=who.headers)
    assert r.status_code == 200, r.text
    return dict(r.json())


def _correct(client: TestClient, who: Staff, item_id: str, **body: Any) -> Any:
    return client.post(f"/v1/studio/items/{item_id}/score-corrections", headers=who.headers, json=body)


def test_rehearsal_disputed_question_soft_then_void(client: TestClient, physics: dict[str, Any]) -> None:
    """Runbook `disputed-question.md`: report, SOFT (no score change), confirmed VOID, EXCLUDE as a new version."""
    learner = _learner(client)
    a, item_ids = _finish_all_correct(client, learner, physics)
    disputed = item_ids[1]
    before = _result(client, learner, a["id"])
    assert (before["raw"], before["maximum"], before["version"]) == (POOL, POOL, 1)
    report = client.post(
        "/v1/support/tickets",
        headers=learner.headers,
        json={
            "category": "academic_report",
            "subject": "Fixture: question 1 looks wrong",
            "body": "Fixture: none of the options seems right.",
            "reference": {"kind": "attempt", "id": a["id"], "position": 1},
        },
    )
    assert report.status_code == 201, report.text
    pub = physics["publisher"]
    try:
        soft = _post(
            client, pub, disputed, "quarantine", {"reason": f"Fixture report {report.json()['id']}", "level": "SOFT"}
        )
        assert soft.status_code == 200
        assert _result(client, learner, a["id"])["version"] == 1  # suspected only: no scoring change
        adjudicator = _adjudicator(client)
        early = _correct(client, adjudicator, disputed, defect="VOID", reason="Fixture: confirmed no valid option")
        assert early.status_code == 409  # quarantine must be at the matching level first
        void = _post(client, pub, disputed, "quarantine", {"reason": "Fixture: defect confirmed", "level": "VOID"})
        assert void.status_code == 200 and void.json()["quarantine_level"] == "VOID"
        assert (
            _correct(client, _adjudicator(client, mfa=False), disputed, defect="VOID", reason="x" * 12).status_code
            == 403
        )
        done = _correct(client, adjudicator, disputed, defect="VOID", reason="Fixture: confirmed no valid option")
        assert done.status_code == 201, done.text
        assert done.json()["rescored"] >= 1 and done.json()["affected_attempts"] >= 1
        after = _result(client, learner, a["id"])
        assert (after["raw"], after["maximum"], after["version"]) == (POOL - 1, POOL - 1, 2)  # EXCLUDE for practice
        assert after["items"][0]["treatment"] == "EXCLUDE" and after["revision_reason"]
        assert after["revised_at"] is not None
        notes = [n["event"] for n in client.get("/v1/me/notifications", headers=learner.headers).json()["items"]]
        assert notes.count("score.revised") == 1
        # Rerunning propagation (the recovery CLI path) adds nothing.
        with get_sessionmaker()() as db:
            assert adjudications.propagate(db, uuid.UUID(done.json()["version_id"])) == 0
            versions = db.scalars(select(ScoreVersion.version).where(ScoreVersion.attempt_id == uuid.UUID(a["id"])))
            assert sorted(versions) == [1, 2]
        # A corrected question stays out of learners' hands until a corrected version is published.
        assert _post(client, pub, disputed, "release", {"reason": "Fixture: try release"}).status_code == 409
    finally:
        with get_sessionmaker()() as db:  # leave the shared fixture pool usable for other tests in this module
            db.execute(text("update mcq_adjudication set status = 'superseded' where item_id = :i"), {"i": disputed})
            db.commit()
        _post(client, pub, disputed, "release", {"reason": "Fixture cleanup"})


def test_key_correction_regrades_and_supersedes_explicitly(client: TestClient, physics: dict[str, Any]) -> None:
    learner = _learner(client)
    a, item_ids = _finish_all_correct(client, learner, physics)
    item = item_ids[2]
    published_key = _keys(a["form_id"])[2]
    other = next(o for o in ("o1", "o2", "o3", "o4") if o != published_key)
    pub = physics["publisher"]
    adjudicator = _adjudicator(client)
    try:
        assert (
            _post(client, pub, item, "quarantine", {"reason": "Fixture: key error", "level": "KEY_ERROR"}).status_code
            == 200
        )
        same = _correct(
            client, adjudicator, item, defect="KEY_ERROR", corrected_option_id=published_key, reason="x" * 12
        )
        assert same.status_code == 422
        bad = _correct(client, adjudicator, item, defect="KEY_ERROR", corrected_option_id="nope", reason="x" * 12)
        assert bad.status_code == 422
        first = _correct(
            client, adjudicator, item, defect="KEY_ERROR", corrected_option_id=other, reason="Fixture: key is wrong"
        )
        assert first.status_code == 201, first.text
        r = _result(client, learner, a["id"])
        row = r["items"][1]
        assert row["treatment"] == "KEY_CORRECTION" and row["correct_option_id"] == other and row["earned"] == 0
        assert (r["raw"], r["maximum"], r["version"]) == (POOL - 1, POOL, 2)
        again = _correct(
            client, adjudicator, item, defect="KEY_ERROR", corrected_option_id=other, reason="Fixture again"
        )
        assert again.status_code == 409  # identical correction already effective
        # Re-classified as VOID: supersedes the key correction explicitly; one effective correction per version.
        assert (
            _post(client, pub, item, "quarantine", {"reason": "Fixture: actually void", "level": "VOID"}).status_code
            == 200
        )
        void = _correct(client, adjudicator, item, defect="VOID", reason="Fixture: no valid option after all")
        assert void.status_code == 201 and void.json()["supersedes_id"] == first.json()["id"]
        history = client.get(f"/v1/studio/items/{item}/score-corrections", headers=adjudicator.headers).json()
        mine = [h for h in history if h["id"] in (first.json()["id"], void.json()["id"])]  # the shared pool may
        assert [h["status"] for h in mine] == ["superseded", "effective"]  # hold earlier corrections of this item
        r3 = _result(client, learner, a["id"])
        assert (r3["raw"], r3["maximum"], r3["version"]) == (POOL - 1, POOL - 1, 3)
    finally:
        with get_sessionmaker()() as db:
            db.execute(text("update mcq_adjudication set status = 'superseded' where item_id = :i"), {"i": item})
            db.commit()
        _post(client, pub, item, "release", {"reason": "Fixture cleanup"})


def test_an_attempt_open_during_a_correction_gets_it_at_submission(client: TestClient, physics: dict[str, Any]) -> None:
    learner = _learner(client)
    form = _form(client, learner, physics["chapter"], count=POOL).json()
    a = _start(client, learner, form["id"])
    item_ids = _form_item_ids(form["id"])
    item = item_ids[3]
    pub = physics["publisher"]
    try:
        assert _post(client, pub, item, "quarantine", {"reason": "Fixture: void", "level": "VOID"}).status_code == 200
        done = _correct(client, _adjudicator(client), item, defect="VOID", reason="Fixture: confirmed void")
        assert done.status_code == 201
        keys = _keys(form["id"])
        ops = [_op(p, 1, keys[p]) for p in sorted(item_ids)]
        assert _save_ops(client, learner, a["id"], *ops).status_code == 200
        client.post(
            f"/v1/attempts/{a['id']}/submit",
            headers=learner.headers,
            json={"idempotency_key": uuid.uuid4().hex, "ops": []},
        )
        r = _result(client, learner, a["id"])
        assert (r["raw"], r["maximum"], r["version"]) == (POOL - 1, POOL - 1, 1) and r["revision_reason"] is None
    finally:
        with get_sessionmaker()() as db:
            db.execute(text("update mcq_adjudication set status = 'superseded' where item_id = :i"), {"i": item})
            db.commit()
        _post(client, pub, item, "release", {"reason": "Fixture cleanup"})


def test_an_unstarted_test_with_a_question_under_review_does_not_start(
    client: TestClient, physics: dict[str, Any]
) -> None:
    """§5.7 before start, and the P08.S4.T2 affected report (counts only)."""
    learner = _learner(client)
    form = _form(client, learner, physics["chapter"], count=POOL).json()
    item = _form_item_ids(form["id"])[1]
    pub = physics["publisher"]
    try:
        assert (
            _post(client, pub, item, "quarantine", {"reason": "Fixture: suspected", "level": "SOFT"}).status_code == 200
        )
        r = client.post(f"/v1/practice/forms/{form['id']}/attempt", headers=learner.headers)
        assert r.status_code == 409 and r.json()["code_reason"] == "FORM_SUPERSEDED"
        report = client.get(f"/v1/studio/items/{item}/affected", headers=pub.headers)
        assert report.status_code == 200, report.text
        assert report.json()[-1]["before_start"] >= 1
        assert set(report.json()[-1]) == {"version", "status", "before_start", "active", "released"}
        learner_view = client.get(f"/v1/studio/items/{item}/affected", headers=learner.headers)
        assert learner_view.status_code == 403
    finally:
        _post(client, pub, item, "release", {"reason": "Fixture: not a defect"})
    assert client.post(f"/v1/practice/forms/{form['id']}/attempt", headers=learner.headers).status_code == 200
