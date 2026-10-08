"""W06.S2.T3: rubric adjudications across attempts. A published rubric correction is applied to earlier work only by an
academic adjudicator; marks carry forward only when the scoring basis is identical, other scored questions go to a
teacher, and pending or unmarked questions are re-targeted. Real PostgreSQL; technical fixtures only (each test
publishes its own question in its own chapter so the shared fixture rubric never changes)."""

from __future__ import annotations

import copy
import threading
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from portal_api.modules.written import adjudication
from tests.test_content_workflow import Staff, _chapter, _confirm_rights, _post, _refs
from tests.test_written_attempts import _learner, _map, _png, _seal, _upload
from tests.test_written_records import QUESTION, R_CHECKS, W_CHECKS, _rubric

SCOPE = {"grades": [12], "subjects": ["chemistry"]}


class Team:
    def __init__(self, client: TestClient, chapter_index: int, subject: str = "chemistry") -> None:
        self.client = client
        self.subject = subject
        self.scope = scope = {"grades": [12], "subjects": [subject]}
        with get_sessionmaker()() as db:
            self.author = Staff(client, db, ["content_author"], scope)
            self.reviewer = Staff(client, db, ["subject_reviewer"], scope)
            self.publisher = Staff(client, db, ["publisher"], scope, mfa=True)
            self.adjudicator = Staff(client, db, ["academic_adjudicator"], scope, mfa=True)  # W06-01
            self.marker = Staff(client, db, ["subject_reviewer"], scope)
            chapter, doc = _chapter(db, 12, subject, chapter_index)
            _confirm_rights(client, db, doc)
            from portal_api.modules.written.review import ReviewCapacity

            if db.get(ReviewCapacity, (12, subject)) is None:
                db.add(ReviewCapacity(grade_number=12, subject_code=subject, max_open_cases=10_000, reason="fixture"))
                db.commit()
        self.chapter, self.doc = chapter, doc
        q = client.post(
            "/v1/studio/items",
            headers=self.author.headers,
            json={"kind": "written", "chapter_id": str(chapter.id), "title": "Fixture"},
        ).json()
        client.put(
            f"/v1/studio/items/{q['id']}/draft",
            headers=self.author.headers,
            json={"revision": q["working"]["revision"], "body": QUESTION, "source_refs": _refs(chapter, doc)},
        )
        assert _post(client, self.author, q["id"], "submit").status_code == 200
        q = _post(
            client,
            self.reviewer,
            q["id"],
            "review",
            {"decision": "approve", "comment": "Fixture check", "checklist": W_CHECKS},
        ).json()
        assert "working" in q, q
        self.question_version = q["working"]["id"]
        r = client.post(
            "/v1/studio/items",
            headers=self.author.headers,
            json={"kind": "rubric", "parent_item_id": q["id"], "title": "Rubric"},
        ).json()
        self.rubric_id = r["id"]
        self.body = _rubric(self.question_version)
        client.put(
            f"/v1/studio/items/{r['id']}/draft",
            headers=self.author.headers,
            json={"revision": r["working"]["revision"], "body": self.body, "source_refs": _refs(chapter, doc)},
        )
        self._approve_publish(r["id"])
        assert _post(client, self.publisher, q["id"], "publish").status_code == 200

    def _approve_publish(self, item_id: str) -> None:
        assert _post(self.client, self.author, item_id, "submit").status_code == 200
        ok = _post(
            self.client,
            self.reviewer,
            item_id,
            "review",
            {"decision": "approve", "comment": "Fixture check", "checklist": R_CHECKS},
        )
        assert ok.status_code == 200, ok.text
        assert _post(self.client, self.publisher, item_id, "publish").status_code == 200

    def correct_rubric(self, change: Any) -> str:
        """Publish a corrected rubric version through the editorial workflow; returns its version id."""
        rev = _post(self.client, self.author, self.rubric_id, "revise", {"reason": "Fixture rubric correction"})
        assert rev.status_code == 200, rev.text
        body = copy.deepcopy(self.body)
        change(body)
        self.body = body
        saved = self.client.put(
            f"/v1/studio/items/{self.rubric_id}/draft",
            headers=self.author.headers,
            json={
                "revision": rev.json()["working"]["revision"],
                "body": body,
                "source_refs": _refs(self.chapter, self.doc),
            },
        )
        assert saved.status_code == 200, saved.text
        self._approve_publish(self.rubric_id)
        item = self.client.get(f"/v1/studio/items/{self.rubric_id}", headers=self.author.headers).json()
        return str((item["published"] or item["working"])["id"])  # after publication the working version is it

    def sealed(self, seed: int) -> tuple[Staff, dict[str, Any]]:
        learner = _learner(self.client)
        f = self.client.post(
            "/v1/written/forms",
            headers={**learner.headers, "Idempotency-Key": uuid.uuid4().hex},
            json={"grade": 12, "subject": self.subject, "chapter_ids": [str(self.chapter.id)], "question_count": 1},
        )
        assert f.status_code == 201, f.text
        started = self.client.post(f"/v1/written/forms/{f.json()['id']}/attempt", headers=learner.headers)
        assert started.status_code == 200, started.text
        a = dict(started.json())
        page = _upload(self.client, learner, a["id"], _png(seed=seed)).json()["pages"][0]["id"]
        m = _map(self.client, learner, a, {k: {"pages": [page]} for k in ("1:a", "1:b")}).json()
        assert _seal(self.client, learner, a["id"], m["manifest_revision"]).status_code == 200
        return learner, a

    def case(self, attempt_id: str, kind: str) -> dict[str, Any]:
        row = next(
            c
            for c in self.client.get("/v1/studio/written/queue", headers=self.marker.headers).json()
            if c["reference"] == attempt_id[:8] and c["case_kind"] == kind
        )
        return dict(self.client.get(f"/v1/studio/written/cases/{row['id']}", headers=self.marker.headers).json())

    def decide(self, attempt_id: str, kind: str, **body: Any) -> Any:
        c = self.case(attempt_id, kind)
        v = self.client.post(f"/v1/studio/written/cases/{c['id']}/lease", headers=self.marker.headers).json()["version"]
        return self.client.post(
            f"/v1/studio/written/cases/{c['id']}/decision",
            headers=self.marker.headers,
            json={"expected_version": v, "release": True, **body},
        )

    def adjudicate(self, **body: Any) -> Any:
        return self.client.post(
            "/v1/studio/written/adjudications",
            headers=self.adjudicator.headers,
            json={"rubric_item_id": self.rubric_id, "reason": "Fixture: the published guide had an error.", **body},
        )

    def run(self, adj_id: str) -> dict[str, Any]:
        """Queue the correction (MFA adjudicator), let the worker drain the queue, and return the job's final state."""
        from portal_api.modules.written import regrade_jobs

        r = self.client.post(f"/v1/studio/written/adjudications/{adj_id}/run", headers=self.adjudicator.headers)
        assert r.status_code == 202, r.text
        with get_sessionmaker()() as db:
            regrade_jobs.work(db, batch=50)
        job = self.client.get(f"/v1/studio/written/regrade-jobs/{r.json()['id']}", headers=self.adjudicator.headers)
        assert job.status_code == 200, job.text
        return dict(job.json())


AW = {"1": {"a1": {"units": 100, "reason": "Fixture"}, "b1": {"units": 150, "reason": "Fixture"}, "b2": {"units": 0}}}


def _result(client: TestClient, who: Staff, attempt_id: str) -> dict[str, Any]:
    return dict(client.get(f"/v1/written-attempts/{attempt_id}/result", headers=who.headers).json())


def _count(sql: str, **params: Any) -> int:
    with get_sessionmaker()() as db:
        return int(db.execute(text(sql), params).scalar() or 0)


def test_an_identical_scoring_basis_carries_human_marks_forward_once(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    team = Team(client, 8)
    learner, a = team.sealed(seed=1501)
    assert team.decide(a["id"], "initial", awards=AW).status_code == 200
    before = _result(client, learner, a["id"])
    # only a reviewer note changes: the scoring basis is identical
    new = team.correct_rubric(lambda b: b["expected_concepts"].append("Fixture: a further concept to look for"))

    # only an adjudicator in scope may apply a correction to earlier work
    assert (
        client.post(
            "/v1/studio/written/adjudications",
            headers=team.marker.headers,
            json={"rubric_item_id": team.rubric_id, "reason": "Fixture: the published guide had an error."},
        ).status_code
        == 403
    )
    adj = team.adjudicate()
    assert adj.status_code == 201, adj.text
    body = adj.json()
    assert [c["carry_forward"] for c in body["compatibility"].values()] == [True]
    assert body["impact"]["total_attempts"] >= 1 and body["impact"]["remaining"] == body["impact"]["total_attempts"]

    out = team.run(body["id"])
    assert out["processed"] >= 1 and out["remaining"] == 0
    after = _result(client, learner, a["id"])
    assert after["version"] == before["version"] + 1
    assert after["decision_method"] == "SYSTEM"
    assert (after["total_units"], after["questions"]) == (before["total_units"], before["questions"])
    assert [h["case_kind"] for h in after["history"]] == ["initial", "regrade"]
    assert len(after["notices"]) == 1 and "unchanged" in after["notices"][0]["message"]
    with get_sessionmaker()() as db:
        sv = db.execute(
            text(
                "select rubric_version_ids, regrade_detail from written_score_version "
                "where attempt_id = :a and version = :v"
            ),
            {"a": a["id"], "v": after["version"]},
        ).one()
    assert sv[0]["1"] == new and sv[1]["compatibility"] == "scoring_basis_identical"

    # idempotent: a second run, or a run racing another, adds nothing
    assert team.run(body["id"])["processed"] == 0
    assert _result(client, learner, a["id"])["version"] == after["version"]
    assert _count("select count(*) from written_notice where attempt_id = :a", a=a["id"]) == 1
    # nothing was consumed or released by the regrade
    assert _count("select count(*) from allowance_event where attempt_id = :a and kind = 'CONSUMED'", a=a["id"]) == 1


def test_a_changed_scoring_basis_goes_to_a_teacher_never_a_machine_overwrite(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    team = Team(client, 9)
    learner, a = team.sealed(seed=1511)
    assert team.decide(a["id"], "initial", awards=AW).status_code == 200
    before = _result(client, learner, a["id"])

    def clarify(b: dict[str, Any]) -> None:
        b["criteria"][0]["description"] = "Fixture criterion a1, corrected: credit the equivalent unit form"

    new = team.correct_rubric(clarify)
    adj = team.adjudicate().json()
    assert [c["carry_forward"] for c in adj["compatibility"].values()] == [False]
    assert adj["compatibility"][next(iter(adj["compatibility"]))]["criteria"]["a1"] == "changed"
    out = team.run(adj["id"])
    assert out["processed"] >= 1
    # the released result is untouched until a teacher re-marks; the learner is told
    held = _result(client, learner, a["id"])
    assert (held["version"], held["total_units"]) == (before["version"], before["total_units"])
    assert "re-mark question 1" in held["notices"][0]["message"]
    case = team.case(a["id"], "regrade")
    assert case["regrade"]["positions"] == [1]
    assert case["questions"][0]["rubric_version_id"] == new  # marked under the corrected rubric
    # a regrade can't park the question as pending
    bad = team.decide(
        a["id"], "regrade", awards={}, question_status={"1": {"status": "pending", "reason": "Fixture reason"}}
    )
    assert bad.status_code == 422
    done = team.decide(a["id"], "regrade", awards=AW)
    assert done.status_code == 200, done.text
    final = _result(client, learner, a["id"])
    assert final["decision_method"] == "TEACHER" and final["history"][-1]["case_kind"] == "regrade"
    assert _count("select count(*) from allowance_event where attempt_id = :a and kind = 'CONSUMED'", a=a["id"]) == 1


def test_pending_and_unmarked_questions_are_retargeted_and_superseding_is_explicit(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    team = Team(client, 10)
    learner, a = team.sealed(seed=1521)  # not marked yet
    _, b = team.sealed(seed=1522)
    pending = {"1": {"status": "pending", "reason": "Fixture: can't read it", "learner_action": "rescan"}}
    assert team.decide(b["id"], "initial", awards={}, question_status=pending).status_code == 200
    v2 = team.correct_rubric(lambda body: body["criteria"][0].update(description="Fixture a1, second wording"))
    first = team.adjudicate().json()
    v3 = team.correct_rubric(lambda body: body["criteria"][0].update(description="Fixture a1, third wording"))
    # v1 is already claimed by an active correction: replacing it must be explicit
    again = team.adjudicate()
    assert again.status_code == 409 and again.json()["code_reason"] == "SUPERSEDE_REQUIRED"
    chained = team.adjudicate(from_version_ids=[v2])  # v2 -> v3 is a separate, chained correction
    assert chained.status_code == 201, chained.text
    out = team.run(first["id"])
    assert out["processed"] >= 2
    # the complete effective set applies: v1 -> v2 -> v3 in one step
    assert team.case(a["id"], "initial")["questions"][0]["rubric_version_id"] == v3
    assert team.case(b["id"], "completion")["questions"][0]["rubric_version_id"] == v3
    assert _result(client, learner, a["id"])["status"] == "pending"
    # the chained correction's own run finds nothing left to change for these attempts
    assert team.run(chained.json()["id"])["regraded"] == 0


def test_concurrent_runs_regrade_each_attempt_once(client: TestClient, published_written: dict[str, Any]) -> None:
    team = Team(client, 11)
    learners = []
    for seed in (1531, 1532, 1533):
        learner, a = team.sealed(seed=seed)
        assert team.decide(a["id"], "initial", awards=AW).status_code == 200
        learners.append((learner, a))
    team.correct_rubric(lambda b: b["expected_concepts"].append("Fixture: another concept"))
    adj_id = uuid.UUID(team.adjudicate().json()["id"])
    barrier = threading.Barrier(2)
    results: list[dict[str, Any]] = []

    def worker() -> None:
        with get_sessionmaker()() as db:
            barrier.wait(timeout=10)
            results.append(adjudication.process_batch(db, adj_id, 50))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(60)
    assert len(results) == 2
    for learner, a in learners:
        r = _result(client, learner, a["id"])
        assert [h["case_kind"] for h in r["history"]] == ["initial", "regrade"], r["history"]
        assert len(r["notices"]) == 1
    assert (
        _count(
            "select count(*) from written_rubric_regrade where adjudication_id = :j and status = 'done'", j=str(adj_id)
        )
        == 3
    )


def test_an_open_recheck_is_retargeted_instead_of_a_second_case(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    team = Team(client, 12)
    learner, a = team.sealed(seed=1541)
    assert team.decide(a["id"], "initial", awards=AW).status_code == 200
    asked = client.post(
        f"/v1/written-attempts/{a['id']}/recheck",
        headers=learner.headers,
        json={"reason": "Fixture: please look at part (a) again.", "positions": [1]},
    )
    assert asked.status_code == 200, asked.text
    recheck_version = team.case(a["id"], "recheck")["version"]
    new = team.correct_rubric(lambda b: b["criteria"][0].update(description="Fixture a1, corrected wording"))
    adj = team.adjudicate().json()
    team.run(adj["id"])
    with get_sessionmaker()() as db:
        outcomes = db.execute(
            text("select outcomes from written_rubric_regrade where attempt_id = :a"), {"a": a["id"]}
        ).scalar()
    assert outcomes == {"1": "review_in_open_case"}
    queue = client.get("/v1/studio/written/queue", headers=team.marker.headers).json()
    assert not [c for c in queue if c["reference"] == a["id"][:8] and c["case_kind"] == "regrade"]
    rc = team.case(a["id"], "recheck")
    assert rc["version"] == recheck_version + 1  # a stale save on the recheck now conflicts
    assert rc["questions"][0]["rubric_version_id"] == new  # and it is marked under the corrected rubric
