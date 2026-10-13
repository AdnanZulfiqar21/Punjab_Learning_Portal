"""W05.S3.T2-T3 (AUTO-PROVENANCE-01): provenance, unexpected model changes, and MCQ work unaffected by failures.

* Every assessed record keeps which assessor and version was configured, which model actually answered (or that
  the provider didn't say), a configuration hash, request and output hashes, latency and provider-reported usage.
* If a different model answers than the qualified one, nothing it said becomes a proposal.
* While the assessor fails every call, learners' MCQ practice carries on and is scored.

Uses the deterministic technical fixture assessor (no provider is configured, B10) and fixture scripts and
questions; the stage records created here are removed afterwards.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from portal_api.db import get_sessionmaker
from portal_api.modules.written import automatic
from portal_api.modules.written.automatic import AutoAssessment
from tests.test_attempts import _form, _learner, _op, _save_ops, _start
from tests.test_mcq_corrections import _keys
from tests.test_written_automatic import Scripted, _run
from tests.test_written_marking import _sealed_script


def _rows(attempt_id: str, assessor: str) -> list[AutoAssessment]:
    with get_sessionmaker()() as db:
        return list(
            db.scalars(
                select(AutoAssessment).where(
                    AutoAssessment.attempt_id == uuid.UUID(attempt_id), AutoAssessment.assessor == assessor
                )
            )
        )


def _cleanup(name: str) -> None:
    with get_sessionmaker()() as db:
        db.execute(delete(AutoAssessment).where(AutoAssessment.assessor == name))
        db.commit()


def test_provenance_is_recorded_and_a_changed_model_proposes_nothing(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    fixture = automatic.FixtureAssessor()
    reported = Scripted(lambda r: {**fixture.assess(r), "served_by": "1", "usage": {"input": 1200, "output": 80}})
    reported.name = f"fx-prov-{uuid.uuid4().hex[:8]}"
    changed = Scripted(lambda r: {**fixture.assess(r), "served_by": "2-unqualified"})
    changed.name = f"fx-model-{uuid.uuid4().hex[:8]}"
    reported.version = changed.version = "1"  # the qualified model version
    try:
        _, a = _sealed_script(client, published_written["chapter"])
        assert set(_run(a["id"], reported)) <= {"proposed", "review"}
        rows = _rows(a["id"], reported.name)
        assert rows
        for row in rows:
            p = row.provenance
            assert (p["assessor"], p["assessor_version"], p["served_by"]) == (reported.name, "1", "1")
            assert p["usage"] == {"input": 1200, "output": 80} and p["latency_ms"] >= 0
            assert len(p["config_hash"]) == len(p["request_hash"]) == len(p["output_hash"]) == 64
        assert len({r.provenance["config_hash"] for r in rows}) == 1  # one configuration for the whole run

        _, b = _sealed_script(client, published_written["chapter"])
        assert set(_run(b["id"], changed)) == {"rejected"}
        for row in _rows(b["id"], changed.name):
            assert row.proposal == {} and "not the qualified 1" in row.errors[0]
            assert row.provenance["served_by"] == "2-unqualified"  # kept as evidence of what happened
    finally:
        _cleanup(reported.name)
        _cleanup(changed.name)


def test_a_failing_assessor_never_blocks_mcq_practice(
    client: TestClient, published_written: dict[str, Any], physics: dict[str, Any]
) -> None:
    def down(request: dict[str, Any]) -> dict[str, Any]:
        raise TimeoutError("fixture: the provider times out on every call")

    failing = Scripted(down)
    failing.name = f"fx-down-{uuid.uuid4().hex[:8]}"
    try:
        _, a = _sealed_script(client, published_written["chapter"])
        outcomes = _run(a["id"], failing)
        assert outcomes and set(outcomes) <= {"queued", "failed"}  # retried later or dead-lettered, never a mark
        assert all(r.proposal == {} for r in _rows(a["id"], failing.name))

        learner = _learner(client)  # meanwhile, MCQ practice works and is scored
        form = _form(client, learner, physics["chapter"], count=2).json()
        attempt = _start(client, learner, form["id"])
        keys = _keys(form["id"])
        assert _save_ops(client, learner, attempt["id"], *[_op(p, 1, k) for p, k in keys.items()]).status_code == 200
        done = client.post(
            f"/v1/attempts/{attempt['id']}/submit",
            headers=learner.headers,
            json={"idempotency_key": uuid.uuid4().hex, "ops": []},
        )
        assert done.status_code == 200
        result = client.get(f"/v1/attempts/{attempt['id']}/result", headers=learner.headers).json()
        assert (result["raw"], result["maximum"]) == (2, 2)
    finally:
        _cleanup(failing.name)
