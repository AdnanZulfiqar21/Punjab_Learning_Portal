"""PR #31 review corrections: RS31-01 (retry-safe rescans), RS31-02 (durable deadline), RS31-03 (post-cutoff truth) and
the evidence-to-score provenance check. Real PostgreSQL; technical fixtures only."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from portal_api.modules.written import rescans
from tests.test_content_workflow import Staff
from tests.test_written_attempts import _learner, _map, _png, _seal, _shift, _start, _upload

SCOPE = {"grades": [12], "subjects": ["chemistry"]}


def _staff(client: TestClient) -> Staff:
    with get_sessionmaker()() as db:
        return Staff(client, db, ["subject_reviewer"], SCOPE)


def _aw(**units: int) -> dict[str, Any]:
    return {k[1:]: {"a1": {"units": v}, "b1": {"units": 0}, "b2": {"units": 0}} for k, v in units.items()}


def _sealed(
    client: TestClient, chapter: str, seed: int, writing_minutes: int | None = None
) -> tuple[Staff, dict[str, Any]]:
    learner = _learner(client)
    extra = {"writing_minutes": writing_minutes} if writing_minutes else {}
    a = _start(client, learner, chapter, question_count=2, **extra)
    page = _upload(client, learner, a["id"], _png(seed=seed)).json()["pages"][0]["id"]
    m = _map(client, learner, a, {k: {"pages": [page]} for k in ("1:a", "1:b", "2:a", "2:b")}).json()
    assert _seal(client, learner, a["id"], m["manifest_revision"]).status_code == 200
    return learner, a


def _decide(client: TestClient, who: Staff, attempt_id: str, kind: str, **body: Any) -> Any:
    case = next(
        c
        for c in client.get("/v1/studio/written/queue", headers=who.headers).json()
        if c["reference"] == attempt_id[:8] and c["case_kind"] == kind
    )
    v = client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=who.headers).json()["version"]
    return client.post(
        f"/v1/studio/written/cases/{case['id']}/decision",
        headers=who.headers,
        json={"expected_version": v, "release": True, **body},
    )


def _pending(action: str | None) -> dict[str, Any]:
    st: dict[str, Any] = {"status": "pending", "reason": "Fixture: answer 2 can't be read"}
    if action:
        st["learner_action"] = action
    return {"2": st}


def _rescan(client: TestClient, who: Staff, attempt_id: str, data: bytes, key: str | None = None) -> Any:
    return client.post(
        f"/v1/written-attempts/{attempt_id}/questions/2/rescan",
        params={"note": "Fixture: clearer copy"},
        headers={**who.headers, "Content-Type": "application/octet-stream", "Idempotency-Key": key or uuid.uuid4().hex},
        content=data,
    )


def _deadline(client: TestClient, learner: Staff, attempt_id: str) -> str:
    r = client.get(f"/v1/written-attempts/{attempt_id}/result", headers=learner.headers).json()
    return str(r["questions"][1]["action_deadline"])


def _revisions(attempt_id: str) -> int:
    with get_sessionmaker()() as db:
        return int(
            db.execute(
                text("select count(*) from written_evidence_revision where attempt_id = :a"), {"a": attempt_id}
            ).scalar()
            or 0
        )


# ------------------------------------------------------------------ RS31-01
def test_simultaneous_identical_rescans_admit_one_and_answer_the_other(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=1101)
    t = _staff(client)
    assert (
        _decide(client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_pending("rescan")).status_code
        == 200
    )
    data = _png(seed=1102)
    barrier = threading.Barrier(2)
    real_inspect = rescans.evidence.inspect

    def synced(*args: Any) -> Any:
        out = real_inspect(*args)
        barrier.wait(timeout=10)  # both requests finish parsing before either takes the lock
        return out

    rescans.evidence.inspect = synced  # type: ignore[assignment]
    try:
        codes: list[int] = []
        threads = [
            threading.Thread(target=lambda k=k: codes.append(_rescan(client, learner, a["id"], data, k).status_code))
            for k in (uuid.uuid4().hex, uuid.uuid4().hex)
        ]
        for th in threads:
            th.start()
        for th in threads:
            th.join(60)
    finally:
        rescans.evidence.inspect = real_inspect  # type: ignore[assignment]
    assert sorted(codes) == [201, 409], codes  # never a 500
    assert _revisions(a["id"]) == 1
    with get_sessionmaker()() as db:  # the winner's stored objects are intact
        key = db.execute(
            text(
                "select f.storage_key from written_evidence_revision r join written_file f on f.id = r.file_id "
                "where r.attempt_id = :a"
            ),
            {"a": a["id"]},
        ).scalar()
    from portal_api.modules.written import storage

    assert storage.get_store().exists(str(key))


def test_a_retried_rescan_returns_the_original_acknowledgement(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=1103)
    t = _staff(client)
    assert (
        _decide(client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_pending("rescan")).status_code
        == 200
    )
    key, data = uuid.uuid4().hex, _png(seed=1104)
    first = _rescan(client, learner, a["id"], data, key)
    assert first.status_code == 201, first.text
    again = _rescan(client, learner, a["id"], data, key)  # the response was lost; the app retries
    assert again.status_code == 200 and again.json()["id"] == first.json()["id"] and again.json()["replay"] is True
    changed = _rescan(client, learner, a["id"], _png(seed=1105), key)
    assert changed.status_code == 409 and changed.json()["code_reason"] == "KEY_REUSED"
    with get_sessionmaker()() as db:  # even after the deadline, the exact retry still gets its acknowledgement
        db.execute(
            text(
                "update written_learner_obligation set deadline = clock_timestamp() - interval '1 hour' "
                "where attempt_id = :a"
            ),
            {"a": a["id"]},
        )
        db.commit()
    late = _rescan(client, learner, a["id"], data, key)
    assert late.status_code == 200 and late.json()["id"] == first.json()["id"]
    assert _revisions(a["id"]) == 1
    sealed_original = _rescan(client, learner, a["id"], _png(seed=1103))
    assert sealed_original.status_code == 409  # a new request resending the original photo is still refused
    no_key = client.post(
        f"/v1/written-attempts/{a['id']}/questions/2/rescan",
        headers={**learner.headers, "Content-Type": "application/octet-stream"},
        content=_png(seed=1106),
    )
    assert no_key.status_code == 422


def test_a_repeated_confirmation_is_answered_without_a_second_resolution(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=1107)
    t = _staff(client)
    assert (
        _decide(
            client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_pending("confirm_or_rescan")
        ).status_code
        == 200
    )
    url = f"/v1/written-attempts/{a['id']}/questions/2/confirm-unanswered"
    assert client.post(url, headers=learner.headers).status_code == 204
    assert client.post(url, headers=learner.headers).status_code == 204  # retry: already confirmed
    with get_sessionmaker()() as db:
        versions = db.execute(
            text("select count(*) from written_score_version where attempt_id = :a and decision_method = 'LEARNER'"),
            {"a": a["id"]},
        ).scalar()
        released = db.execute(
            text("select count(*) from allowance_event where attempt_id = :a and kind = 'RELEASED' and position = 2"),
            {"a": a["id"]},
        ).scalar()
    assert versions == 1 and released == 1


# ------------------------------------------------------------------ RS31-02
def test_the_first_deadline_survives_action_changes_and_omissions(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=1108)
    t = _staff(client)
    assert (
        _decide(client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_pending("rescan")).status_code
        == 200
    )
    first = _deadline(client, learner, a["id"])
    for action in ("confirm_or_rescan", None, "rescan", "confirm_or_rescan"):
        r = _decide(client, t, a["id"], "completion", awards={}, question_status=_pending(action))
        assert r.status_code == 200, r.text
        if action:
            assert _deadline(client, learner, a["id"]) == first, action


def test_a_timely_rescan_is_not_treated_as_silence_while_staff_review_is_pending(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=1109)
    t = _staff(client)
    assert (
        _decide(client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_pending("rescan")).status_code
        == 200
    )
    assert _rescan(client, learner, a["id"], _png(seed=1110)).status_code == 201
    with get_sessionmaker()() as db:
        db.execute(
            text(
                "update written_learner_obligation set deadline = clock_timestamp() - interval '1 hour' "
                "where attempt_id = :a"
            ),
            {"a": a["id"]},
        )
        db.commit()
        assert rescans.expire_learner_actions(db) == 0  # the learner answered in time; staff review is outstanding
    r = client.get(f"/v1/written-attempts/{a['id']}/result", headers=learner.headers).json()
    assert r["questions"][1]["status"] == "pending"


# ------------------------------------------------------------------ RS31-03
def test_post_cutoff_is_computed_from_the_pinned_upload_cutoff(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=1111)  # sealed early: U is still ahead
    t = _staff(client)
    assert (
        _decide(client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_pending("rescan")).status_code
        == 200
    )
    assert _rescan(client, learner, a["id"], _png(seed=1112)).status_code == 201
    _shift(a["id"], cutoff_offset_s=-60)  # now U has passed
    assert _rescan(client, learner, a["id"], _png(seed=1113)).status_code == 201
    with get_sessionmaker()() as db:
        rows = db.execute(
            text("select post_cutoff from written_evidence_revision where attempt_id = :a order by created_at"),
            {"a": a["id"]},
        ).all()
        audits = db.execute(
            text(
                "select details->>'post_cutoff' from audit_event where target_id = :a "
                "and action = 'written.rescan_submitted' "
                "order by at"
            ),
            {"a": a["id"]},
        ).all()
    assert [r[0] for r in rows] == [False, True]
    assert [x[0] for x in audits] == ["false", "true"]  # stored evidence and audit provenance agree


def test_the_cutoff_boundary_is_not_post_cutoff() -> None:
    u = datetime(2026, 10, 8, 12, 0, 0)
    assert rescans.is_post_cutoff(u, u) is False
    assert rescans.is_post_cutoff(u + timedelta(microseconds=1), u) is True


# ------------------------------------------------------------------ evidence provenance (section 4)
def test_a_mark_names_the_readability_copies_it_used_and_unsuitable_copies_cannot_be_used(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=1114)
    t = _staff(client)
    assert (
        _decide(client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_pending("rescan")).status_code
        == 200
    )
    good = _rescan(client, learner, a["id"], _png(seed=1115)).json()["id"]
    bad = _rescan(client, learner, a["id"], _png(seed=1116)).json()["id"]
    classes = {
        good: {"class": "READABILITY", "reason": "Fixture: same working, clearer"},
        bad: {"class": "NEW_CONTENT", "reason": "Fixture: different working"},
    }
    wrong = _decide(
        client, t, a["id"], "completion", awards=_aw(q2=200), classifications=classes, evidence={"2": [bad]}
    )
    assert wrong.status_code == 422 and wrong.json()["code_reason"] == "EVIDENCE_NOT_ELIGIBLE"
    ok = _decide(client, t, a["id"], "completion", awards=_aw(q2=200), classifications=classes, evidence={"2": [good]})
    assert ok.status_code == 200, ok.text
    with get_sessionmaker()() as db:
        used = db.execute(
            text(
                "select evidence_revisions from written_score_version where attempt_id = :a "
                "order by version desc limit 1"
            ),
            {"a": a["id"]},
        ).scalar()
    assert [e["id"] for e in used["2"]] == [good] and len(used["2"][0]["sha256"]) == 64
    # A later recheck of question 1 carries question 2's provenance forward unchanged.
    assert (
        client.post(
            f"/v1/written-attempts/{a['id']}/recheck",
            headers=learner.headers,
            json={"reason": "Fixture: please look at question 1 again", "positions": [1]},
        ).status_code
        == 200
    )
    assert _decide(client, _staff(client), a["id"], "recheck", awards=_aw(q1=200)).status_code == 200
    with get_sessionmaker()() as db:
        latest = db.execute(
            text(
                "select evidence_revisions from written_score_version where attempt_id = :a "
                "order by version desc limit 1"
            ),
            {"a": a["id"]},
        ).scalar()
    assert [e["id"] for e in latest["2"]] == [good]


def test_readable_originals_can_be_marked_despite_an_unsuitable_copy(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    learner, a = _sealed(client, published_written["chapter"], seed=1117)
    t = _staff(client)
    assert (
        _decide(client, t, a["id"], "initial", awards=_aw(q1=100), question_status=_pending("rescan")).status_code
        == 200
    )
    bad = _rescan(client, learner, a["id"], _png(seed=1118)).json()["id"]
    r = _decide(
        client,
        t,
        a["id"],
        "completion",
        awards=_aw(q2=100),  # marked from the sealed original, no copy used
        classifications={bad: {"class": "INDETERMINATE", "reason": "Fixture: can't compare"}},
    )
    assert r.status_code == 200, r.text
