"""PR #32 review corrections: PR32-01 (an open learner request stays usable when a later decision omits its action),
PR32-02 (staff drafts keep every editable intent and may propose a classification without approving it), PR32-03
(concurrent linked-form preparation with one key) and PR32-04 (authoritative cutoff timing for clearer copies).
Real PostgreSQL; technical fixtures only."""

from __future__ import annotations

import threading
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from portal_api.modules.written import rescans, service
from tests.test_content_workflow import Staff
from tests.test_linked_attempts import _link
from tests.test_rescan_corrections import _aw, _decide, _pending, _rescan, _sealed, _staff
from tests.test_written_attempts import _png


def _result(client: TestClient, who: Staff, attempt_id: str) -> dict[str, Any]:
    return dict(client.get(f"/v1/written-attempts/{attempt_id}/result", headers=who.headers).json())


def _case(client: TestClient, who: Staff, attempt_id: str, kind: str) -> dict[str, Any]:
    row = next(
        c
        for c in client.get("/v1/studio/written/queue", headers=who.headers).json()
        if c["reference"] == attempt_id[:8] and c["case_kind"] == kind
    )
    return dict(client.get(f"/v1/studio/written/cases/{row['id']}", headers=who.headers).json())


def _scalar(sql: str, **params: Any) -> Any:
    with get_sessionmaker()() as db:
        return db.execute(text(sql), params).scalar()


# ------------------------------------------------------------------ PR32-01
def test_omitting_the_action_keeps_the_open_request_usable_with_its_first_deadline(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=1401)
    t = _staff(client)
    assert (
        _decide(client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_pending("rescan")).status_code
        == 200
    )
    first = _result(client, learner, a["id"])["questions"][1]
    assert first["learner_action"] == "rescan" and first["action_deadline"]
    # a completion decision keeps the question pending but doesn't repeat the action
    assert _decide(client, t, a["id"], "completion", awards={}, question_status=_pending(None)).status_code == 200
    q2 = _result(client, learner, a["id"])["questions"][1]
    assert q2["status"] == "pending"
    assert (q2["learner_action"], q2["action_deadline"]) == ("rescan", first["action_deadline"])
    # the learner can still answer, and the request's deadline did not move
    assert _rescan(client, learner, a["id"], _png(seed=1402)).status_code == 201
    assert _scalar("select count(*) from written_learner_obligation where attempt_id = :a", a=a["id"]) == 1


def test_an_expired_request_after_a_reviewed_response_does_not_claim_silence(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=1403)
    t = _staff(client)
    assert (
        _decide(client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_pending("rescan")).status_code
        == 200
    )
    assert _rescan(client, learner, a["id"], _png(seed=1404)).status_code == 201
    with get_sessionmaker()() as db:
        rev = str(rescans.revisions_for(db, uuid.UUID(a["id"]))[0].id)
    still = _decide(
        client,
        t,
        a["id"],
        "completion",
        awards={},
        question_status=_pending(None),
        classifications={rev: {"class": "INDETERMINATE", "reason": "Fixture: still too unclear to compare"}},
    )
    assert still.status_code == 200, still.text
    with get_sessionmaker()() as db:
        db.execute(
            text(
                "update written_learner_obligation set deadline = clock_timestamp() - interval '1 hour' "
                "where attempt_id = :a"
            ),
            {"a": a["id"]},
        )
        db.commit()
        assert rescans.expire_learner_actions(db) == 1
    q2 = _result(client, learner, a["id"])["questions"][1]
    assert q2["status"] == "unavailable"
    assert "No clearer copy arrived" not in q2["status_reason"]  # the learner did respond in time


# ------------------------------------------------------------------ PR32-02
def test_a_draft_can_propose_a_readability_copy_without_approving_it_and_reloads_complete(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=1411)
    t = _staff(client)
    assert (
        _decide(client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_pending("rescan")).status_code
        == 200
    )
    assert _rescan(client, learner, a["id"], _png(seed=1412)).status_code == 201
    with get_sessionmaker()() as db:
        rev = str(rescans.revisions_for(db, uuid.UUID(a["id"]))[0].id)
    before = _result(client, learner, a["id"])
    obligations = _scalar("select count(*) from written_learner_obligation where attempt_id = :a", a=a["id"])
    allowance = _scalar("select count(*) from allowance_event where attempt_id = :a", a=a["id"])
    proposal = {rev: {"class": "READABILITY", "reason": "Fixture: same working, sharper photo"}}
    draft = _decide(
        client,
        t,
        a["id"],
        "completion",
        release=False,
        awards=_aw(q2=200),
        classifications=proposal,
        evidence={"2": [rev]},
    )
    assert draft.status_code == 200, draft.text
    # a proposal is not an approval: nothing is classified, published, charged or put on a clock
    assert _scalar("select classification from written_evidence_revision where id = :r", r=rev) is None
    assert _result(client, learner, a["id"]) == before
    assert _scalar("select count(*) from written_learner_obligation where attempt_id = :a", a=a["id"]) == obligations
    assert _scalar("select count(*) from allowance_event where attempt_id = :a", a=a["id"]) == allowance
    # reload: every editable intent comes back
    detail = _case(client, t, a["id"], "completion")
    assert detail["draft"] == {
        "question_status": {},
        "classifications": proposal,
        "evidence": {"2": [rev]},
    }
    assert detail["latest"]["awards"]["2"]["a1"]["units"] == 200
    # release still validates and then pins the evidence
    final = _decide(
        client, t, a["id"], "completion", awards=_aw(q2=200), classifications=proposal, evidence={"2": [rev]}
    )
    assert final.status_code == 200, final.text
    assert _scalar("select classification from written_evidence_revision where id = :r", r=rev) == "READABILITY"


def test_a_saved_mixed_draft_reopens_pending_with_its_reason_and_action(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=1413)
    t = _staff(client)
    pending = _pending("confirm_or_rescan")
    r = _decide(client, t, a["id"], "initial", release=False, awards=_aw(q1=100), question_status=pending)
    assert r.status_code == 200, r.text
    assert _result(client, learner, a["id"])["status"] == "pending"  # nothing released
    assert _scalar("select count(*) from written_learner_obligation where attempt_id = :a", a=a["id"]) == 0
    detail = _case(client, t, a["id"], "initial")
    st = detail["draft"]["question_status"]
    assert st == {"2": {"status": "pending", "reason": pending["2"]["reason"], "learner_action": "confirm_or_rescan"}}
    assert detail["draft"]["classifications"] == {} and detail["draft"]["evidence"] == {}


def test_a_draft_cannot_propose_an_unsuitable_or_foreign_copy(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=1415)
    t = _staff(client)
    assert (
        _decide(client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_pending("rescan")).status_code
        == 200
    )
    assert _rescan(client, learner, a["id"], _png(seed=1416)).status_code == 201
    with get_sessionmaker()() as db:
        rev = str(rescans.revisions_for(db, uuid.UUID(a["id"]))[0].id)
    nc = {rev: {"class": "NEW_CONTENT", "reason": "Fixture: different working"}}
    bad = _decide(
        client, t, a["id"], "completion", release=False, awards=_aw(q2=200), classifications=nc, evidence={"2": [rev]}
    )
    assert bad.status_code == 422 and bad.json()["code_reason"] == "EVIDENCE_NOT_ELIGIBLE"
    foreign = _decide(
        client, t, a["id"], "completion", release=False, awards=_aw(q2=200), evidence={"2": [str(uuid.uuid4())]}
    )
    assert foreign.status_code == 422


# ------------------------------------------------------------------ PR32-03
def _race(client: TestClient, learner: Staff, attempt_id: str, key: str, bodies: list[dict[str, Any]]) -> list[Any]:
    barrier = threading.Barrier(2)
    real = service._live_rubric_versions

    def synced(*args: Any) -> Any:
        out = real(*args)
        barrier.wait(timeout=10)  # both requests passed the early key lookup before either inserts
        return out

    service._live_rubric_versions = synced  # type: ignore[assignment]
    out: list[Any] = []
    try:
        threads = [
            threading.Thread(target=lambda b=b: out.append(_link(client, learner, attempt_id, key, **b)))
            for b in bodies
        ]
        for th in threads:
            th.start()
        for th in threads:
            th.join(60)
    finally:
        service._live_rubric_versions = real  # type: ignore[assignment]
    return out


def test_concurrent_preparation_with_one_key_returns_one_form(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=1421)
    assert _decide(client, _staff(client), a["id"], "initial", awards=_aw(q1=100, q2=0)).status_code == 200
    key = uuid.uuid4().hex
    reserved = _scalar("select count(*) from allowance_event where kind = 'RESERVED'")
    body = {"reason": "REWRITE", "positions": [1, 2]}
    out = _race(client, learner, a["id"], key, [body, body])
    assert len(out) == 2, "a request raised instead of answering"
    assert sorted(r.status_code for r in out) == [201, 201], [r.text for r in out]
    assert out[0].json() == out[1].json()
    form = out[0].json()["form_id"]
    assert _scalar("select count(*) from written_form where idempotency_key = :k", k=key) == 1
    assert _scalar("select count(*) from written_form_item where form_id = :f", f=form) == 2
    audit = "select count(*) from audit_event where target_id = :f and action = 'written.linked_form'"
    assert _scalar(audit, f=form) == 1
    assert _scalar("select count(*) from allowance_event where kind = 'RESERVED'") == reserved  # nothing charged


def test_concurrent_preparation_with_one_key_and_different_requests_conflicts_once(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=1423)
    assert _decide(client, _staff(client), a["id"], "initial", awards=_aw(q1=100, q2=0)).status_code == 200
    key = uuid.uuid4().hex
    out = _race(
        client,
        learner,
        a["id"],
        key,
        [{"reason": "REWRITE", "positions": [1]}, {"reason": "REWRITE", "positions": [2]}],
    )
    assert len(out) == 2, "a request raised instead of answering"
    assert sorted(r.status_code for r in out) == [201, 409], [r.text for r in out]
    assert next(r for r in out if r.status_code == 409).json()["code_reason"] == "KEY_REUSED"
    assert _scalar("select count(*) from written_form where idempotency_key = :k", k=key) == 1


# ------------------------------------------------------------------ PR32-04
def test_clearer_copies_show_their_authoritative_cutoff_timing(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=1431)
    t = _staff(client)
    assert (
        _decide(client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_pending("rescan")).status_code
        == 200
    )
    assert _rescan(client, learner, a["id"], _png(seed=1432)).status_code == 201  # the untimed window is still open
    r = _case(client, t, a["id"], "completion")["revisions"][0]
    assert (r["post_cutoff"], r["cutoff_timing"]) == (False, "before_cutoff")
    assert r["upload_cutoff_at"]
