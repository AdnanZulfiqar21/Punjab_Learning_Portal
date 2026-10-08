"""PR #36/#38 review (NEW-11 to NEW-15): MFA on recheck rebase/expansion, crash-safe regrade job progress, open
regrade cases under a superseding correction, explicit descendant policy when an ancestor is superseded, and
order-independent cumulative chains. Real PostgreSQL; technical fixtures only (Class XII Physics chapters, so the
chemistry fixtures used elsewhere are untouched)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from portal_api.modules.written import adjudication, regrade_jobs
from tests.test_content_workflow import Staff
from tests.test_rubric_adjudication import AW, Team, _count, _result
from tests.test_written_attempts import _map, _png, _seal, _upload

EXPIRE = text("update written_regrade_job set lease_expires_at = clock_timestamp() - interval '1 second' where id = :j")


def _scoring(n: str) -> Any:
    return lambda b: b["criteria"][0].update(description=f"Fixture a1, corrected wording {n}")


def _job(team: Team, adj_id: str) -> dict[str, Any]:
    r = team.client.post(f"/v1/studio/written/adjudications/{adj_id}/run", headers=team.adjudicator.headers)
    assert r.status_code == 202, r.text
    return dict(r.json())


def _get_job(team: Team, job_id: str) -> dict[str, Any]:
    return dict(team.client.get(f"/v1/studio/written/regrade-jobs/{job_id}", headers=team.adjudicator.headers).json())


def _v(team: Team, number: int) -> str:
    with get_sessionmaker()() as db:
        return str(
            db.execute(
                text("select id from content_version where item_id = :i and number = :n"),
                {"i": team.rubric_id, "n": number},
            ).scalar()
        )


def _latest(attempt_id: str) -> Any:
    with get_sessionmaker()() as db:
        return db.execute(
            text(
                "select version, rubric_version_ids, effective_adjudication from written_score_version "
                "where attempt_id = :a and released order by version desc limit 1"
            ),
            {"a": attempt_id},
        ).one()


# ------------------------------------------------------------------ NEW-11
def test_recheck_rebase_and_expansion_need_an_mfa_adjudicator(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    team = Team(client, 0, "physics")
    learner, a = team.sealed(seed=1801)
    assert team.decide(a["id"], "initial", awards=AW).status_code == 200
    asked = client.post(
        f"/v1/written-attempts/{a['id']}/recheck",
        headers=learner.headers,
        json={"reason": "Fixture: please look at part (a) again.", "positions": [1]},
    )
    assert asked.status_code == 200, asked.text
    case = team.case(a["id"], "recheck")
    with get_sessionmaker()() as db:
        plain = Staff(client, db, ["academic_adjudicator"], team.scope)  # no MFA
        mfa = Staff(client, db, ["academic_adjudicator"], team.scope, mfa=True)
        other_scope = Staff(client, db, ["academic_adjudicator"], {"grades": [11], "subjects": ["physics"]}, mfa=True)
    body = {"reason": "Fixture: rebase onto the current result."}
    url = f"/v1/studio/written/cases/{case['id']}/rebase"
    no = client.post(url, headers=plain.headers, json=body)
    assert no.status_code == 403 and "multi-factor" in no.json()["detail"], no.text
    assert client.post(url, headers=other_scope.headers, json=body).status_code in (403, 404)
    ok = client.post(url, headers=mfa.headers, json=body)
    assert ok.status_code == 200, ok.text
    with get_sessionmaker()() as db:
        actors = {
            str(x)
            for x in db.execute(
                text(
                    "select actor_user_id from audit_event where action = 'written.recheck_rebased' and target_id = :a"
                ),
                {"a": a["id"]},
            ).scalars()
        }
    assert actors <= {str(mfa.id)}  # only the MFA adjudicator ever rebased it


# ------------------------------------------------------------------ NEW-12
def test_job_progress_survives_a_crash_between_attempt_commits_and_the_counter_update(
    client: TestClient, published_written: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    team = Team(client, 1, "physics")
    for seed in (1811, 1812, 1813):
        _, a = team.sealed(seed=seed)
        assert team.decide(a["id"], "initial", awards=AW).status_code == 200
    team.correct_rubric(lambda b: b["expected_concepts"].append("Fixture: crash"))
    adj = team.adjudicate().json()
    job = _job(team, adj["id"])
    real = adjudication.process_batch

    def crash(*args: Any, **kw: Any) -> Any:
        real(*args, **kw)  # every script commits its own outcome...
        raise RuntimeError("worker killed before updating the job")  # ...then the process dies

    monkeypatch.setattr(adjudication, "process_batch", crash)
    with get_sessionmaker()() as db, pytest.raises(RuntimeError):
        regrade_jobs.run_one_batch(db, "crashing-worker", 50)
    monkeypatch.setattr(adjudication, "process_batch", real)
    with get_sessionmaker()() as db:  # the lease runs out; another worker resumes
        db.execute(
            EXPIRE,
            {"j": job["id"]},
        )
        db.commit()
        regrade_jobs.work(db, batch=50)
    done = _get_job(team, job["id"])
    assert (done["status"], done["processed"], done["regraded"], done["failed"], done["remaining"]) == (
        "succeeded",
        3,
        3,
        0,
        0,
    ), done


def test_a_resumed_job_never_turns_a_failed_script_into_success(
    client: TestClient, published_written: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    team = Team(client, 2, "physics")
    _, a = team.sealed(seed=1821)
    assert team.decide(a["id"], "initial", awards=AW).status_code == 200
    team.correct_rubric(lambda b: b["expected_concepts"].append("Fixture: fail"))
    adj = team.adjudicate().json()
    job = _job(team, adj["id"])
    real_regrade, real_batch = adjudication._regrade_attempt, adjudication.process_batch

    def boom(*args: Any, **kw: Any) -> Any:
        raise RuntimeError("unrelated failure")

    def crash(*args: Any, **kw: Any) -> Any:
        real_batch(*args, **kw)
        raise RuntimeError("worker killed")

    monkeypatch.setattr(adjudication, "_regrade_attempt", boom)
    monkeypatch.setattr(adjudication, "process_batch", crash)
    with get_sessionmaker()() as db, pytest.raises(RuntimeError):
        regrade_jobs.run_one_batch(db, "crashing-worker", 50)
    monkeypatch.setattr(adjudication, "_regrade_attempt", real_regrade)
    monkeypatch.setattr(adjudication, "process_batch", real_batch)
    with get_sessionmaker()() as db:
        db.execute(
            EXPIRE,
            {"j": job["id"]},
        )
        db.commit()
        regrade_jobs.work(db, batch=50)
    done = _get_job(team, job["id"])
    assert (done["status"], done["failed"], done["processed"]) == ("failed", 1, 0), done


# ------------------------------------------------------------------ NEW-13
def test_a_superseding_correction_retargets_the_open_regrade_case(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    team = Team(client, 3, "physics")
    learner, a = team.sealed(seed=1831)
    assert team.decide(a["id"], "initial", awards=AW).status_code == 200
    team.correct_rubric(_scoring("A"))
    first = team.adjudicate().json()
    team.run(first["id"])
    case = team.case(a["id"], "regrade")
    with get_sessionmaker()() as db:
        b_approver = Staff(client, db, ["academic_adjudicator"], team.scope, mfa=True)
    v3 = team.correct_rubric(_scoring("B"))
    second = client.post(
        "/v1/studio/written/adjudications",
        headers=b_approver.headers,
        json={
            "rubric_item_id": team.rubric_id,
            "reason": "Fixture: a better correction of the same version.",
            "from_version_ids": [_v(team, 1)],
            "supersedes_ids": [first["id"]],
            "retain_descendant_ids": [],
        },
    )
    assert second.status_code == 201, second.text
    job = _job(team, second.json()["id"])
    with get_sessionmaker()() as db:
        regrade_jobs.work(db, batch=50)
    assert _get_job(team, job["id"])["status"] == "succeeded"
    with get_sessionmaker()() as db:
        row = db.execute(
            text("select adjudication_id, status from written_review_case where id = :c"), {"c": case["id"]}
        ).one()
        moved = db.execute(
            text(
                "select count(*) from audit_event where action = 'written.regrade_case_retargeted' and target_id = :c"
            ),
            {"c": case["id"]},
        ).scalar()
    assert (str(row.adjudication_id), row.status) == (second.json()["id"], "queued")
    assert moved == 1
    # independence is checked against the effective correction's approver
    assert client.post(f"/v1/studio/written/cases/{case['id']}/lease", headers=b_approver.headers).status_code == 403
    assert team.case(a["id"], "regrade")["questions"][0]["rubric_version_id"] == v3
    assert team.decide(a["id"], "regrade", awards=AW).status_code == 200
    assert _latest(a["id"]).effective_adjudication == {"1": [second.json()["id"]]}
    assert len(_result(client, learner, a["id"])["notices"]) == 2  # one per correction that reached this script


# ------------------------------------------------------------------ NEW-14
def test_superseding_an_ancestor_needs_an_explicit_decision_about_its_descendants(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    team = Team(client, 4, "physics")
    _, early = team.sealed(seed=1841)  # pinned on v1
    assert team.decide(early["id"], "initial", awards=AW).status_code == 200
    v2 = team.correct_rubric(lambda b: b["expected_concepts"].append("Fixture: B"))
    ab = team.adjudicate().json()  # A: v1 -> v2
    _, middle = team.sealed(seed=1842)  # pinned on v2
    assert team.decide(middle["id"], "initial", awards=AW).status_code == 200
    team.correct_rubric(lambda b: b["expected_concepts"].append("Fixture: C"))
    bc = team.adjudicate(from_version_ids=[v2]).json()  # B: v2 -> v3 (chained after A)
    v4 = team.correct_rubric(lambda b: b["expected_concepts"].append("Fixture: D"))
    # Replacing A alone would leave B active with no decision about it: refused, naming B.
    refused = team.adjudicate(from_version_ids=[_v(team, 1)], supersedes_ids=[ab["id"]])
    assert refused.status_code == 409 and refused.json()["code_reason"] == "DESCENDANTS_UNRESOLVED", refused.text
    assert refused.json()["descendants"] == [bc["id"]]
    # Explicitly retained: B keeps serving scripts pinned on v2; v1 scripts follow the replacement.
    ad = team.adjudicate(from_version_ids=[_v(team, 1)], supersedes_ids=[ab["id"]], retain_descendant_ids=[bc["id"]])
    assert ad.status_code == 201, ad.text
    assert ad.json()["retained_descendant_ids"] == [bc["id"]]
    team.run(ad.json()["id"])
    team.run(bc["id"])
    with get_sessionmaker()() as db:
        eff_early = adjudication.effective(db, db.get(adjudication.WrittenAttempt, uuid.UUID(early["id"])))
        eff_middle = adjudication.effective(db, db.get(adjudication.WrittenAttempt, uuid.UUID(middle["id"])))
    assert (eff_early[1][1], eff_early[1][2]) == (v4, [ad.json()["id"]])
    assert eff_middle[1][2] == [bc["id"]]
    assert _latest(early["id"]).rubric_version_ids["1"] == v4


# ------------------------------------------------------------------ NEW-15
def test_a_cumulative_chain_gives_the_same_record_whichever_job_runs_first(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    team = Team(client, 5, "physics")
    from tests.test_written_attempts import _learner

    learner = _learner(client)
    f = client.post(
        "/v1/written/forms",
        headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex},
        json={"grade": 12, "subject": "physics", "chapter_ids": [str(team.chapter.id)], "question_count": 1},
    )
    a = client.post(f"/v1/written/forms/{f.json()['id']}/attempt", headers=learner.headers).json()  # pinned on v1
    v2 = team.correct_rubric(_scoring("2"))
    first = team.adjudicate().json()
    v3 = team.correct_rubric(_scoring("3"))
    second = team.adjudicate(from_version_ids=[v2]).json()
    page = _upload(client, learner, a["id"], _png(seed=1851)).json()["pages"][0]["id"]
    m = _map(client, learner, a, {k: {"pages": [page]} for k in ("1:a", "1:b")}).json()
    assert _seal(client, learner, a["id"], m["manifest_revision"]).status_code == 200  # queues both, in chain order
    with get_sessionmaker()() as db:
        order = [
            str(r)
            for r in db.execute(
                text(
                    "select j.adjudication_id from written_regrade_job j where j.adjudication_id in (:x, :y) "
                    "order by j.created_at, j.id"
                ),
                {"x": first["id"], "y": second["id"]},
            ).scalars()
        ]
        assert order == [first["id"], second["id"]]
        # Run them in the reverse of chain order.
        adjudication.process_batch(db, uuid.UUID(second["id"]), 50)
        adjudication.process_batch(db, uuid.UUID(first["id"]), 50)
    with get_sessionmaker()() as db:
        rows = db.execute(
            text(
                "select adjudication_id::text, status, outcomes from written_rubric_regrade where attempt_id = :a "
                "order by adjudication_id"
            ),
            {"a": a["id"]},
        ).all()
    assert sorted((r[0], r[1]) for r in rows) == sorted([(first["id"], "done"), (second["id"], "done")])
    # The ancestor is recorded as applied through the chain, not as "unaffected".
    assert {r[0]: r[2] for r in rows} == {first["id"]: {"1": "retargeted"}, second["id"]: {"1": "retargeted"}}
    with get_sessionmaker()() as db:
        via = db.execute(
            text("select applied_via::text from written_rubric_regrade where attempt_id = :a and adjudication_id = :x"),
            {"a": a["id"], "x": first["id"]},
        ).scalar()
    assert via == second["id"]
    assert _count("select count(*) from written_notice where attempt_id = :a", a=a["id"]) == 1
    case = team.case(a["id"], "initial")
    assert case["questions"][0]["rubric_version_id"] == v3
    with get_sessionmaker()() as db:
        eff = adjudication.effective(db, db.get(adjudication.WrittenAttempt, uuid.UUID(a["id"])))
    assert eff[1][2] == [first["id"], second["id"]]
    for adj_id in (first["id"], second["id"]):
        impact = client.get(f"/v1/studio/written/adjudications/{adj_id}", headers=team.adjudicator.headers).json()[
            "impact"
        ]
        assert (impact["processed"], impact["remaining"]) == (1, 0), (adj_id, impact)


# ------------------------------------------------------------------ scoped pagination
def test_the_correction_list_applies_scope_before_the_page_limit(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    team = Team(client, 6, "physics")
    _, a = team.sealed(seed=1861)
    assert team.decide(a["id"], "initial", awards=AW).status_code == 200
    team.correct_rubric(lambda b: b["expected_concepts"].append("Fixture: scope"))
    assert team.adjudicate().status_code == 201
    with get_sessionmaker()() as db:
        physics = int(
            db.execute(text("select count(*) from written_rubric_adjudication where subject_code = 'physics'")).scalar()
            or 0
        )
        reader = Staff(client, db, ["subject_reviewer"], team.scope)
    seen: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = client.get(
            "/v1/studio/written/adjudications", params={"offset": offset, "limit": 1}, headers=reader.headers
        ).json()
        if not page:
            break
        seen += page
        offset += 1
    assert len(seen) == physics and {x["subject"] for x in seen} == {"physics"}
