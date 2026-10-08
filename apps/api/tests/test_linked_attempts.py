"""W04.S3.T3: separate new learning attempts (WA-AC24). New or rewritten work goes to a linked new practice attempt with
its own reservation; the original attempt, evidence and result never change.
Real PostgreSQL; technical fixtures only."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from portal_api.db import get_sessionmaker
from portal_api.modules.written import rescans
from tests.test_content_workflow import Staff
from tests.test_rescan_corrections import _aw, _decide, _pending, _rescan, _sealed, _staff
from tests.test_written_attempts import _learner, _map, _png, _seal, _start, _upload


def _link(client: TestClient, who: Staff, attempt_id: str, key: str | None = None, **body: Any) -> Any:
    return client.post(
        f"/v1/written-attempts/{attempt_id}/linked-forms",
        headers={**who.headers, "Idempotency-Key": key or uuid.uuid4().hex},
        json=body,
    )


def _result(client: TestClient, who: Staff, attempt_id: str) -> dict[str, Any]:
    return dict(client.get(f"/v1/written-attempts/{attempt_id}/result", headers=who.headers).json())


def _available(client: TestClient, who: Staff) -> int:
    return int(client.get("/v1/me/access", headers=who.headers).json()["written_allowance"]["available"])


def test_a_rewrite_is_a_new_charged_attempt_and_never_changes_the_original(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=1301)
    early = _link(client, learner, a["id"], reason="REWRITE", positions=[1, 2])
    assert early.status_code == 422 and early.json()["code_reason"] == "RESULT_NOT_RELEASED"  # a recheck route instead

    t = _staff(client)
    assert _decide(client, t, a["id"], "initial", awards=_aw(q1=100, q2=0)).status_code == 200
    before = _result(client, learner, a["id"])
    assert before["linked_attempts"] == []

    key = uuid.uuid4().hex
    r = _link(client, learner, a["id"], key, reason="REWRITE", positions=[2, 1])
    assert r.status_code == 201, r.text
    lf = r.json()
    assert lf["question_count"] == 2 and lf["allowance_units"] > 0 and lf["started_attempt_id"] is None
    assert lf["linked_from"] == {"attempt_id": a["id"], "reason": "REWRITE", "positions": [1, 2]}
    # an exact retry returns the same test; the same key for a different request is refused
    assert _link(client, learner, a["id"], key, reason="REWRITE", positions=[1, 2]).json()["form_id"] == lf["form_id"]
    reused = _link(client, learner, a["id"], key, reason="REWRITE", positions=[1])
    assert reused.status_code == 409 and reused.json()["code_reason"] == "KEY_REUSED"

    # preparing it charges nothing; starting it reserves its own allowance through the ordinary admission path
    available = _available(client, learner)
    assert available == lf["allowance_available"]
    started = client.post(f"/v1/written/forms/{lf['form_id']}/attempt", headers=learner.headers)
    assert started.status_code == 200, started.text
    b = started.json()
    assert b["id"] != a["id"] and b["linked_from"]["attempt_id"] == a["id"]
    assert _available(client, learner) == available - lf["allowance_units"]
    view = client.get(f"/v1/written/linked-forms/{lf['form_id']}", headers=learner.headers).json()
    assert view["started_attempt_id"] == b["id"]

    # the new work is sealed and marked as its own attempt
    page = _upload(client, learner, b["id"], _png(seed=1302)).json()["pages"][0]["id"]
    m = _map(client, learner, b, {k: {"pages": [page]} for k in ("1:a", "1:b", "2:a", "2:b")}).json()
    assert _seal(client, learner, b["id"], m["manifest_revision"]).status_code == 200
    assert _decide(client, t, b["id"], "initial", awards=_aw(q1=200, q2=100)).status_code == 200

    after = _result(client, learner, a["id"])
    for k in ("version", "total_units", "released_at", "questions", "history"):
        assert after[k] == before[k], k  # the original result is untouched
    assert [(x["attempt_id"], x["status"], x["reason"]) for x in after["linked_attempts"]] == [
        (b["id"], "sealed", "REWRITE")
    ]
    assert _result(client, learner, b["id"])["total_units"] != before["total_units"]


def test_new_content_from_a_classified_rescan_links_only_that_question(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=1311)
    t = _staff(client)
    assert (
        _decide(client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_pending("rescan")).status_code
        == 200
    )
    assert _rescan(client, learner, a["id"], _png(seed=1312)).status_code == 201
    with get_sessionmaker()() as db:
        rev = str(rescans.revisions_for(db, uuid.UUID(a["id"]))[0].id)
    # not yet classified: no linked attempt can claim it
    assert _link(client, learner, a["id"], reason="NEW_CONTENT", positions=[2], revision_id=rev).status_code == 422
    assert (
        _decide(
            client,
            t,
            a["id"],
            "completion",
            awards={},
            question_status={"2": {"status": "unavailable", "reason": "Fixture: rescan is new work"}},
            classifications={rev: {"class": "NEW_CONTENT", "reason": "Fixture: working differs from the original"}},
        ).status_code
        == 200
    )
    wrong_reason = _link(client, learner, a["id"], reason="INDETERMINATE", positions=[2], revision_id=rev)
    assert wrong_reason.status_code == 422 and wrong_reason.json()["code_reason"] == "LINK_NOT_ELIGIBLE"
    wrong_question = _link(client, learner, a["id"], reason="NEW_CONTENT", positions=[1], revision_id=rev)
    assert wrong_question.status_code == 422
    missing = _link(client, learner, a["id"], reason="NEW_CONTENT", positions=[2])
    assert missing.status_code == 422
    ok = _link(client, learner, a["id"], reason="NEW_CONTENT", positions=[2], revision_id=rev)
    assert ok.status_code == 201, ok.text
    assert ok.json()["question_count"] == 1 and ok.json()["linked_from"]["positions"] == [2]
    q2 = _result(client, learner, a["id"])["questions"][1]
    assert q2["status"] == "unavailable"  # the original outcome stands


def test_only_the_owner_can_link_a_submitted_test(client: TestClient, published_written: dict[str, Any]) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=1321)
    assert _decide(client, _staff(client), a["id"], "initial", awards=_aw(q1=100, q2=0)).status_code == 200
    other = _learner(client)
    assert _link(client, other, a["id"], reason="REWRITE", positions=[1]).status_code == 404
    bad = _link(client, learner, a["id"], reason="REWRITE", positions=[3])
    assert bad.status_code == 422 and bad.json()["code_reason"] == "LINK_NOT_ELIGIBLE"
    active = _start(client, learner, published_written["chapter"], question_count=1)
    unsealed = _link(client, learner, active["id"], reason="REWRITE", positions=[1])
    assert unsealed.status_code == 422 and unsealed.json()["code_reason"] == "NOT_SEALED"
    assert client.get(f"/v1/written/linked-forms/{active['form_id']}", headers=learner.headers).status_code == 404
