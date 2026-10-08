"""PR #34 review (W06-01 to W06-09) for rubric adjudications across attempts: MFA boundary, pinned basis of active
attempts, immutable effective-adjudication provenance, narrow integrity handling, supersede races, chain validation,
durable jobs and bounded preview. Real PostgreSQL; technical fixtures only."""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text

from portal_api.db import get_sessionmaker
from portal_api.modules.written import adjudication, regrade_jobs
from tests.test_content_workflow import Staff
from tests.test_rubric_adjudication import AW, SCOPE, Team, _count, _result
from tests.test_written_attempts import _map, _png, _seal, _upload


def _scoring_change(n: str) -> Any:
    return lambda b: b["criteria"][0].update(description=f"Fixture a1, corrected wording {n}")


def _latest(attempt_id: str) -> Any:
    with get_sessionmaker()() as db:
        return db.execute(
            text(
                "select version, rubric_version_ids, effective_adjudication, adjudication_hash, decision_method "
                "from written_score_version where attempt_id = :a and released order by version desc limit 1"
            ),
            {"a": attempt_id},
        ).one()


# ------------------------------------------------------------------ W06-01
def test_adjudication_mutations_need_an_mfa_session(client: TestClient, published_written: dict[str, Any]) -> None:
    team = Team(client, 13)
    _, a = team.sealed(seed=1601)
    assert team.decide(a["id"], "initial", awards=AW).status_code == 200
    team.correct_rubric(lambda b: b["expected_concepts"].append("Fixture: another concept"))
    with get_sessionmaker()() as db:
        plain = Staff(client, db, ["academic_adjudicator"], SCOPE)  # no MFA
    body = {"rubric_item_id": team.rubric_id, "reason": "Fixture: the published guide had an error."}
    no = client.post("/v1/studio/written/adjudications", headers=plain.headers, json=body)
    assert no.status_code == 403 and "multi-factor" in no.json()["detail"]
    adj = team.adjudicate()
    assert adj.status_code == 201, adj.text
    assert (
        client.post(f"/v1/studio/written/adjudications/{adj.json()['id']}/run", headers=plain.headers).status_code
        == 403
    )
    queued = client.post(f"/v1/studio/written/adjudications/{adj.json()['id']}/run", headers=team.adjudicator.headers)
    assert queued.status_code == 202 and queued.json()["status"] == "queued"
    # reading stays open to scoped academic staff (markers see why a regrade case exists)
    assert (
        client.get(f"/v1/studio/written/adjudications/{adj.json()['id']}", headers=team.marker.headers).status_code
        == 200
    )


# ------------------------------------------------------------------ W06-02
def test_an_active_attempt_keeps_its_pinned_rubric_until_it_is_sealed(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    team = Team(client, 14)
    from tests.test_written_attempts import _learner, _start

    learner = _learner(client)
    a = _start(client, learner, str(team.chapter.id), question_count=1)  # still writing
    new = team.correct_rubric(_scoring_change("w06-02"))
    adj = team.adjudicate().json()
    job = team.run(adj["id"])
    assert job["status"] == "succeeded"
    # no silent mutation of work in progress: no target, no notice, pinned rubric unchanged
    assert _count("select count(*) from written_rubric_target where attempt_id = :a", a=a["id"]) == 0
    assert _count("select count(*) from written_notice where attempt_id = :a", a=a["id"]) == 0
    page = _upload(client, learner, a["id"], _png(seed=1611)).json()["pages"][0]["id"]
    m = _map(client, learner, a, {k: {"pages": [page]} for k in ("1:a", "1:b")}).json()
    assert _seal(client, learner, a["id"], m["manifest_revision"]).status_code == 200
    # sealing queues the correction for this script; marking on the old basis is refused until it is applied
    pending = team.decide(a["id"], "initial", awards=AW)
    assert pending.status_code == 409 and pending.json()["code_reason"] == "CORRECTION_PENDING"
    with get_sessionmaker()() as db:
        assert regrade_jobs.work(db, batch=50) >= 1
    assert team.case(a["id"], "initial")["questions"][0]["rubric_version_id"] == new
    assert len(_result(client, learner, a["id"])["notices"]) == 1
    assert team.decide(a["id"], "initial", awards=AW).status_code == 200


# ------------------------------------------------------------------ W06-03
def test_released_provenance_is_immutable_across_later_corrections(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    team = Team(client, 15)
    _, a = team.sealed(seed=1621)
    assert team.decide(a["id"], "initial", awards=AW).status_code == 200
    first = _latest(a["id"])
    assert first.effective_adjudication == {"1": []} and len(first.adjudication_hash) == 64
    v2 = team.correct_rubric(_scoring_change("B"))
    ab = team.adjudicate().json()
    v3 = team.correct_rubric(_scoring_change("C"))
    bc = team.adjudicate(from_version_ids=[v2]).json()
    team.run(ab["id"])
    assert team.case(a["id"], "regrade")["questions"][0]["rubric_version_id"] == v3  # A -> B -> C in one step
    assert team.decide(a["id"], "regrade", awards=AW).status_code == 200
    marked = _latest(a["id"])
    assert marked.decision_method == "TEACHER" and marked.rubric_version_ids["1"] == v3
    assert marked.effective_adjudication == {"1": [ab["id"], bc["id"]]}
    team.correct_rubric(_scoring_change("D"))
    cd = team.adjudicate(from_version_ids=[v3]).json()
    team.run(cd["id"])
    with get_sessionmaker()() as db:
        again = db.execute(
            text(
                "select effective_adjudication, adjudication_hash from written_score_version "
                "where attempt_id = :a and version = :v"
            ),
            {"a": a["id"], "v": marked.version},
        ).one()
    assert (again.effective_adjudication, again.adjudication_hash) == (
        marked.effective_adjudication,
        marked.adjudication_hash,
    )
    # the original first-marking version still names no correction
    assert (
        _count(
            "select count(*) from written_score_version where attempt_id = :a and version = :v and "
            "effective_adjudication = '{\"1\": []}'::jsonb",
            a=a["id"],
            v=first.version,
        )
        == 1
    )


# ------------------------------------------------------------------ W06-04
def test_an_unrelated_integrity_failure_fails_the_attempt_visibly(
    client: TestClient, published_written: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    team = Team(client, 16)
    learner, a = team.sealed(seed=1631)
    assert team.decide(a["id"], "initial", awards=AW).status_code == 200
    team.correct_rubric(lambda b: b["expected_concepts"].append("Fixture: one more concept"))
    adj = team.adjudicate().json()
    real = adjudication.record

    def broken(db: Any, **kw: Any) -> None:
        if kw.get("action") == "written.rubric_regraded":
            a_ = db.get(adjudication.WrittenAttempt, uuid.UUID(kw["target_id"]))
            # an unrelated check violation that only surfaces when the attempt's transaction is flushed at commit
            db.add(
                adjudication.WrittenNotice(
                    attempt_id=a_.id, user_id=a_.user_id, cause_id=uuid.uuid4(), kind="bogus", positions=[], message="x"
                )
            )
        real(db, **kw)

    monkeypatch.setattr(adjudication, "record", broken)
    job = team.run(adj["id"])
    assert job["status"] == "failed" and job["failed"] >= 1 and job["last_error"]
    assert _result(client, learner, a["id"])["version"] == 1  # nothing half-published
    monkeypatch.setattr(adjudication, "record", real)
    retried = client.post(f"/v1/studio/written/regrade-jobs/{job['id']}/retry", headers=team.adjudicator.headers)
    assert retried.status_code == 200 and retried.json()["status"] == "queued"
    with get_sessionmaker()() as db:
        regrade_jobs.work(db, batch=50)
    done = client.get(f"/v1/studio/written/regrade-jobs/{job['id']}", headers=team.adjudicator.headers).json()
    assert done["status"] == "succeeded" and done["failed"] == 0
    assert _result(client, learner, a["id"])["version"] == 2


# ------------------------------------------------------------------ W06-05
def test_a_run_overlapping_a_supersede_never_leaves_the_stale_target_final(
    client: TestClient, published_written: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    team = Team(client, 1)
    attempts = []
    for seed in (1641, 1642):
        learner, a = team.sealed(seed=seed)
        assert team.decide(a["id"], "initial", awards=AW).status_code == 200
        attempts.append((learner, a))
    v2 = team.correct_rubric(lambda b: b["expected_concepts"].append("Fixture: O"))
    old = team.adjudicate().json()
    v3 = team.correct_rubric(lambda b: b["expected_concepts"].append("Fixture: N"))
    created: dict[str, Any] = {}
    real = adjudication._publish_carry_forward
    calls = {"n": 0}

    def overlapping(*args: Any, **kw: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:  # while the old run holds its first attempt, an adjudicator supersedes it
            th = threading.Thread(
                target=lambda: created.update(
                    r=team.adjudicate(from_version_ids=[_v1(team)], supersedes_ids=[old["id"]])
                )
            )
            th.start()
            created["thread"] = th
            time.sleep(0.5)  # the creator now waits on the per-rubric lock this run holds
        return real(*args, **kw)

    monkeypatch.setattr(adjudication, "_publish_carry_forward", overlapping)
    job = team.run(old["id"])
    created["thread"].join(30)
    monkeypatch.setattr(adjudication, "_publish_carry_forward", real)
    assert created["r"].status_code == 201, created["r"].text
    assert job["status"] in ("superseded", "succeeded")
    new = created["r"].json()
    team.run(new["id"])
    for _, a in attempts:
        latest = _latest(a["id"])
        assert latest.rubric_version_ids["1"] == v3, "a stale superseded target remained final"
        assert latest.effective_adjudication == {"1": [new["id"]]}
    assert v2 != v3


def _v1(team: Team) -> str:
    with get_sessionmaker()() as db:
        return str(
            db.execute(
                text("select id from content_version where item_id = :i order by number limit 1"), {"i": team.rubric_id}
            ).scalar()
        )


def test_a_chain_cycle_or_overlength_is_an_explicit_error() -> None:
    def adj(frm: str, to: str) -> Any:
        a = adjudication.RubricAdjudication(id=uuid.uuid4(), from_version_ids=[frm], to_version_id=uuid.UUID(to))
        return a

    x, y = str(uuid.uuid4()), str(uuid.uuid4())
    with pytest.raises(adjudication.ChainError):
        adjudication.chain([adj(x, y), adj(y, x)], x)
    ids = [str(uuid.uuid4()) for _ in range(adjudication.MAX_CHAIN + 2)]
    with pytest.raises(adjudication.ChainError):
        adjudication.chain([adj(ids[i], ids[i + 1]) for i in range(len(ids) - 1)], ids[0])


# ------------------------------------------------------------------ independence
def test_the_approving_adjudicator_cannot_mark_the_regrade_it_caused(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    team = Team(client, 3)
    _, a = team.sealed(seed=1651)
    assert team.decide(a["id"], "initial", awards=AW).status_code == 200
    team.correct_rubric(_scoring_change("independence"))
    adj = team.adjudicate().json()
    team.run(adj["id"])
    case = team.case(a["id"], "regrade")
    lease = client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=team.adjudicator.headers)
    assert lease.status_code == 403


# ------------------------------------------------------------------ W06-08/09
def test_preview_is_bounded_and_counts_are_exact(client: TestClient, published_written: dict[str, Any]) -> None:
    def prepared(chapter: int, seeds: list[int]) -> tuple[Team, dict[str, Any]]:
        team = Team(client, chapter)
        for seed in seeds:
            _, a = team.sealed(seed=seed)
            assert team.decide(a["id"], "initial", awards=AW).status_code == 200
        team.correct_rubric(lambda b: b["expected_concepts"].append("Fixture: P"))
        return team, team.adjudicate().json()

    def queries(team: Team, adj_id: str) -> int:
        n = {"q": 0}
        engine = get_sessionmaker()().get_bind()

        def count(*_: Any) -> None:
            n["q"] += 1

        event.listen(engine, "before_cursor_execute", count)
        try:
            r = client.get(f"/v1/studio/written/adjudications/{adj_id}", headers=team.adjudicator.headers)
            assert r.status_code == 200
        finally:
            event.remove(engine, "before_cursor_execute", count)
        return n["q"]

    small, small_adj = prepared(5, [1661])
    big, big_adj = prepared(6, [1662, 1663, 1664, 1665])
    assert queries(big, big_adj["id"]) == queries(small, small_adj["id"])  # independent of affected scripts
    url = f"/v1/studio/written/adjudications/{big_adj['id']}"
    impact = client.get(url, headers=big.adjudicator.headers).json()["impact"]
    assert (impact["total_attempts"], impact["processed"], impact["remaining"]) == (4, 0, 4)
    job = big.run(big_adj["id"])
    assert (job["status"], job["processed"], job["remaining"], job["failed"]) == ("succeeded", 4, 0, 0)
    impact = client.get(url, headers=big.adjudicator.headers).json()["impact"]
    assert (impact["total_attempts"], impact["processed"], impact["remaining"], impact["failed"]) == (4, 4, 0, 0)
    assert impact["applied_outcomes"] == {"carried": 4}
    page = client.get(f"{url}/attempts", params={"limit": 3}, headers=big.adjudicator.headers).json()
    assert len(page["items"]) == 3 and page["total"] == 4
