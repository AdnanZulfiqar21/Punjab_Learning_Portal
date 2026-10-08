"""OCT8-05: a seal with every question declared unanswered settles its reservation (technical fixtures only)."""

from __future__ import annotations

import threading
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from tests.test_content_workflow import Staff
from tests.test_written_attempts import _learner, _map, _png, _seal, _start, _upload

SCOPE = {"grades": [12], "subjects": ["chemistry"]}


def _ledger(attempt_id: str) -> list[tuple[str, int | None, int]]:
    with get_sessionmaker()() as db:
        rows = db.execute(
            text("select kind, position, units from allowance_event where attempt_id = :a order by kind, position"),
            {"a": attempt_id},
        ).all()
    return [(k, p, u) for k, p, u in rows]


def _allowance(client: TestClient, who: Staff) -> dict[str, int]:
    return dict(client.get("/v1/me/access", headers=who.headers).json()["written_allowance"])


def _unanswered(client: TestClient, who: Staff, chapter: str) -> tuple[dict[str, Any], dict[str, Any]]:
    a = _start(client, who, chapter, question_count=2)
    m = _map(client, who, a, {k: {"unanswered": True} for k in ("1:a", "1:b", "2:a", "2:b")}).json()
    return a, m


def test_an_all_unanswered_seal_releases_its_reservation(client: TestClient, published_written: dict[str, Any]) -> None:
    who = _learner(client)
    before = _allowance(client, who)
    a, m = _unanswered(client, who, published_written["chapter"])
    assert _allowance(client, who)["reserved"] > 0
    key = uuid.uuid4().hex
    assert _seal(client, who, a["id"], m["manifest_revision"], key).status_code == 200
    after = _allowance(client, who)
    assert after["reserved"] == 0 and after["available"] == before["available"]
    assert [k for k, _, _ in _ledger(a["id"])] == ["RELEASED", "RESERVED"]
    assert _seal(client, who, a["id"], m["manifest_revision"], key).json()["replay"]  # exact retry
    assert [k for k, _, _ in _ledger(a["id"])] == ["RELEASED", "RESERVED"]  # no second settlement


def test_concurrent_all_unanswered_seals_settle_once(client: TestClient, published_written: dict[str, Any]) -> None:
    who = _learner(client)
    a, m = _unanswered(client, who, published_written["chapter"])
    key = uuid.uuid4().hex
    barrier = threading.Barrier(3)
    codes: list[int] = []

    def go() -> None:
        barrier.wait()
        codes.append(_seal(client, who, a["id"], m["manifest_revision"], key).status_code)

    threads = [threading.Thread(target=go) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    assert codes == [200, 200, 200]
    assert sum(1 for k, _, _ in _ledger(a["id"]) if k == "RELEASED") == 1


def test_a_later_zero_mark_release_consumes_nothing_and_mixed_scripts_still_accept(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    who = _learner(client)
    a, m = _unanswered(client, who, published_written["chapter"])
    assert _seal(client, who, a["id"], m["manifest_revision"]).status_code == 200
    with get_sessionmaker()() as db:
        teacher = Staff(client, db, ["subject_reviewer"], SCOPE)
    case = next(
        c
        for c in client.get("/v1/studio/written/queue", headers=teacher.headers).json()
        if c["reference"] == a["id"][:8]
    )
    v = client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=teacher.headers).json()["version"]
    zero = {p: {"a1": {"units": 0}, "b1": {"units": 0}, "b2": {"units": 0}} for p in ("1", "2")}
    r = client.post(
        f"/v1/studio/written/cases/{case['id']}/decision",
        headers=teacher.headers,
        json={"expected_version": v, "release": True, "awards": zero},
    )
    assert r.status_code == 200, r.text
    assert not any(k == "CONSUMED" for k, _, _ in _ledger(a["id"]))  # declared unanswered: never charged
    # A mixed script still accepts exactly its answered question.
    b = _start(client, who, published_written["chapter"], question_count=2)
    page = _upload(client, who, b["id"], _png(seed=951)).json()["pages"][0]["id"]
    mb = _map(
        client,
        who,
        b,
        {"1:a": {"pages": [page]}, "1:b": {"pages": [page]}, "2:a": {"unanswered": True}, "2:b": {"unanswered": True}},
    ).json()
    assert _seal(client, who, b["id"], mb["manifest_revision"]).status_code == 200
    assert [(k, p) for k, p, _ in _ledger(b["id"])] == [("ACCEPTED", 1), ("RESERVED", None)]


def test_repair_settles_already_affected_reservations_once(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    from portal_api.modules.written import review

    who = _learner(client)
    a, m = _unanswered(client, who, published_written["chapter"])
    assert _seal(client, who, a["id"], m["manifest_revision"]).status_code == 200
    with get_sessionmaker()() as db:  # recreate the pre-fix state: sealed, reserved, never settled
        db.execute(text("delete from allowance_event where attempt_id = :a and kind = 'RELEASED'"), {"a": a["id"]})
        db.commit()
    assert _allowance(client, who)["reserved"] > 0
    with get_sessionmaker()() as db:
        assert a["id"] in review.repair_empty_reservations(db)
        assert review.repair_empty_reservations(db) == []  # idempotent
    assert _allowance(client, who)["reserved"] == 0
    with get_sessionmaker()() as db:
        detail = db.execute(
            text("select detail->>'reason' from allowance_event where attempt_id = :a and kind = 'RELEASED'"),
            {"a": a["id"]},
        ).scalar()
    assert "repair" in detail
