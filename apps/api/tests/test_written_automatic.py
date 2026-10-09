"""W05 (AUTOASSESS-01): automatic-assessment contracts and job integrity with the deterministic technical fixture
assessor and injected failures. Nothing here assesses a real script; no provider is configured (B10)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from portal_api.config import ConfigurationError, Settings
from portal_api.db import get_sessionmaker
from portal_api.modules.written import automatic
from portal_api.modules.written.automatic import AutoAssessment
from portal_api.modules.written.models import WrittenReceipt
from portal_api.modules.written.review import WrittenScoreVersion
from tests.test_content_workflow import Staff
from tests.test_written_marking import _sealed_script


class Scripted:
    """An injectable assessor: returns (or raises) whatever the test scripts, recording each request."""

    name = "fixture"
    version = "test"

    def __init__(self, fn: Any) -> None:
        self.fn = fn
        self.requests: list[dict[str, Any]] = []

    def assess(self, request: dict[str, Any]) -> dict[str, Any]:
        self.requests.append(request)
        result: dict[str, Any] = self.fn(request)
        return result


def _rows(attempt_id: str) -> list[AutoAssessment]:
    with get_sessionmaker()() as db:
        return list(db.scalars(select(AutoAssessment).where(AutoAssessment.attempt_id == uuid.UUID(attempt_id))))


def _run(attempt_id: str, assessor: Any) -> list[str]:
    """Enqueue this script and process its rows (not other tests' queued rows)."""
    out = []
    with get_sessionmaker()() as db:
        automatic.enqueue(db, uuid.UUID(attempt_id), assessor)
        db.commit()
        for row in _rows(attempt_id):
            if row.status != "queued":
                continue
            claimed = db.scalar(select(AutoAssessment).where(AutoAssessment.id == row.id).with_for_update())
            assert claimed is not None
            claimed.status, claimed.attempts = "running", claimed.attempts + 1
            db.commit()
            out.append(automatic.process(db, row.id, assessor))
    return out


def test_disabled_by_default_and_fixture_refused_in_production(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    _, a = _sealed_script(client, published_written["chapter"])
    with get_sessionmaker()() as db:
        assert automatic.adapter_for().name == "none"
        assert automatic.enqueue(db, uuid.UUID(a["id"])) == 0  # nothing recorded, nothing sent (B10)
        assert automatic.run_once(db) == {}
    assert _rows(a["id"]) == []
    with pytest.raises(ConfigurationError, match="written_assessor fixture"):
        Settings(role="production", written_assessor="fixture")  # type: ignore[call-arg]


def test_fixture_proposal_is_validated_bound_to_evidence_and_never_published(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    _, a = _sealed_script(client, published_written["chapter"])
    assessor = Scripted(automatic.FixtureAssessor().assess)
    outcomes = _run(a["id"], assessor)
    assert outcomes and set(outcomes) == {"proposed"}
    request = assessor.requests[0]
    assert request["evidence"]["untrusted"] is True and "email" not in str(request).lower()
    row = _rows(a["id"])[0]
    assert row.provenance["request_hash"] and row.provenance["assessor"] == "fixture"
    assert row.proposal["total_units"] >= 0 and set(row.proposal["awards"]) >= {"a1"}
    with get_sessionmaker()() as db:  # proposals never become results: only the teacher route publishes
        versions = db.scalars(
            select(WrittenScoreVersion).where(WrittenScoreVersion.attempt_id == uuid.UUID(a["id"]))
        ).all()
        assert all(v.decision_method != "AI" for v in versions)
    # A duplicate delivery of the same sealed question creates nothing new.
    with get_sessionmaker()() as db:
        assert automatic.enqueue(db, uuid.UUID(a["id"]), assessor) == 0


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda o: {**o, "extra": 1}, "rejected"),  # strict schema
        (lambda o: {**o, "criteria": [{**c, "criterion_id": "zz"} for c in o["criteria"]]}, "rejected"),
        (lambda o: {**o, "criteria": [{**c, "units": 37} for c in o["criteria"]]}, "rejected"),  # not a permitted level
        (
            lambda o: {**o, "criteria": [{**c, "evidence": [{"page_id": str(uuid.uuid4())}]} for c in o["criteria"]]},
            "rejected",
        ),  # anchor on a page that isn't this question's sealed evidence
        (lambda o: {**o, "unresolved": [{"kind": "unreadable", "detail": "smudged"}]}, "review"),
        (lambda o: {**o, "unresolved": [{"kind": "blank"}]}, "review"),  # blank-looking is never inferred as zero
    ],
)
def test_invalid_or_uncertain_outputs_never_become_proposals(
    client: TestClient, published_written: dict[str, Any], mutate: Any, expected: str
) -> None:
    _, a = _sealed_script(client, published_written["chapter"])
    fixture = automatic.FixtureAssessor()
    outcomes = _run(a["id"], Scripted(lambda r: mutate(fixture.assess(r))))
    assert outcomes and set(outcomes) == {expected}
    for row in _rows(a["id"]):
        assert row.proposal == {}
        assert row.errors if expected == "rejected" else row.flags


def test_provider_failures_retry_then_dead_letter_and_unavailable_is_visible(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    _, a = _sealed_script(client, published_written["chapter"])

    def broken(_: dict[str, Any]) -> dict[str, Any]:
        raise TimeoutError("provider timed out")

    for _ in range(automatic.MAX_ATTEMPTS):
        with get_sessionmaker()() as db:
            for row in _rows(a["id"]):
                db.execute(
                    AutoAssessment.__table__.update()
                    .where(AutoAssessment.id == row.id)
                    .values(next_attempt_at=AutoAssessment.created_at)
                )
            db.commit()
        _run(a["id"], Scripted(broken))
    rows = _rows(a["id"])
    assert rows and all(r.status == "failed" and "provider timed out" in (r.last_error or "") for r in rows)
    operator = None
    with get_sessionmaker()() as db:
        operator = Staff(client, db, ["platform_operator"], mfa=True)
        receipt = db.scalar(select(WrittenReceipt).where(WrittenReceipt.attempt_id == uuid.UUID(a["id"])))
        assert receipt is not None
    ops = client.get("/v1/ops/written/auto-assessments", headers=operator.headers).json()
    assert any(d["id"] == str(rows[0].id) for d in ops["dead_letters"])
    url = f"/v1/ops/written/auto-assessments/{rows[0].id}/requeue"
    assert client.post(url, headers=operator.headers).status_code == 204
    assert client.post(url, headers=operator.headers).status_code == 409
    # An unconfigured provider leaves a visible "unavailable" status, not a failure in the script.
    out = _run(a["id"], Scripted(lambda r: automatic.UnconfiguredAssessor().assess(r)))
    assert out == ["unavailable"]
