"""P03.S4.T2 (CORRELATION-01): one correlation ID traces a request through the audit entries it writes, the job rows it
queues and the background work those jobs do. Fixture accounts only."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api import observability
from portal_api.db import get_sessionmaker
from portal_api.modules.audit.models import record
from tests.test_attempts import _learner
from tests.test_exports import _work


def _audit_cids(target_id: str) -> dict[str, str | None]:
    with get_sessionmaker()() as db:
        rows = db.execute(
            text("select action, correlation_id from audit_event where target_id = :t"), {"t": target_id}
        ).all()
    return {a: c for a, c in rows}


def test_an_export_carries_its_request_id_into_the_job_and_the_workers_audit_entries(client: TestClient) -> None:
    learner = _learner(client)
    cid = f"fixture-{uuid.uuid4().hex[:16]}"
    queued = client.post(
        "/v1/exports",
        headers={**learner.headers, observability.HEADER: cid},
        json={"kind": "personal_data", "params": {}},
    )
    assert queued.status_code == 202, queued.text
    assert queued.headers[observability.HEADER] == cid  # echoed, so a client can quote it
    job_id = queued.json()["id"]
    with get_sessionmaker()() as db:
        stored = db.execute(text("select correlation_id from export_job where id = :i"), {"i": job_id}).scalar_one()
    assert stored == cid
    assert observability.current_correlation() is None  # nothing leaks out of the request

    assert _work(job_id)["status"] == "ready"  # the worker runs the job under the request's ID
    assert _audit_cids(job_id).get("export.ready") == cid


def test_an_invalid_header_is_replaced_and_the_new_id_is_used_throughout(client: TestClient) -> None:
    learner = _learner(client)
    r = client.post(
        "/v1/exports",
        headers={**learner.headers, observability.HEADER: "bad id with spaces"},
        json={"kind": "personal_data", "params": {}},
    )
    assert r.status_code == 202
    cid = r.headers[observability.HEADER]
    assert cid != "bad id with spaces" and len(cid) == 32
    with get_sessionmaker()() as db:
        stored = db.execute(
            text("select correlation_id from export_job where id = :i"), {"i": r.json()["id"]}
        ).scalar_one()
    assert stored == cid


def test_binding_is_scoped_and_an_explicit_id_wins() -> None:
    assert observability.current_correlation() is None
    with observability.bind_correlation("outer-fixture"):
        with observability.bind_correlation("inner-fixture"):
            assert observability.current_correlation() == "inner-fixture"
        assert observability.current_correlation() == "outer-fixture"
        with get_sessionmaker()() as db:
            implicit = record(db, actor=None, action="fixture.correlation", target_type="fixture", target_id="x")
            explicit = record(
                db,
                actor=None,
                action="fixture.correlation",
                target_type="fixture",
                target_id="y",
                correlation_id="given",
            )
            assert (implicit.correlation_id, explicit.correlation_id) == ("outer-fixture", "given")
            db.rollback()  # nothing is kept
    assert observability.current_correlation() is None
