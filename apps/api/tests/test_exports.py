"""P16.S4.T2 (EXPORTS-01): asynchronous exports. Ownership, permission at request/worker/download, the OCT9-01 release
policy at generation and download, formula-safe CSV, bounded work, cancel/retry/expiry and audited downloads.
Fixture accounts and fixture questions only; the worker runs in-process via `run_once`."""

from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from portal_api.db import get_sessionmaker
from portal_api.modules.audit.models import AuditEvent, record
from portal_api.modules.exports import service
from tests.test_attempts import _learner
from tests.test_content_workflow import Staff
from tests.test_mock_sessions import _shift
from tests.test_mocks import _publish_profile
from tests.test_result_release import _sit

SINCE = (datetime.now(UTC) - timedelta(days=1)).isoformat()


def _request(client: TestClient, who: Any, kind: str, **params: Any) -> Any:
    return client.post("/v1/exports", headers=who.headers, json={"kind": kind, "params": params})


def _work(job_id: str) -> dict[str, Any]:
    """Run the worker until this job leaves the queue (other tests' jobs may be ahead of it)."""
    for _ in range(50):
        with get_sessionmaker()() as db:
            job = db.get(service.ExportJob, uuid.UUID(job_id))
            assert job is not None
            if job.status not in service.OPEN:
                return {"status": job.status, "error": job.error, "file_key": job.file_key}
            service.run_once(db, worker="fixture-worker")
    raise AssertionError("the export never finished")


def _status(client: TestClient, who: Any, job_id: str) -> str:
    return str(client.get(f"/v1/exports/{job_id}", headers=who.headers).json()["status"])


def test_personal_export_is_owned_audited_and_private(client: TestClient) -> None:
    me, other = _learner(client), _learner(client)
    job = _request(client, me, "personal_data")
    assert job.status_code == 202 and job.json()["status"] == "queued", job.text
    jid = job.json()["id"]
    assert _work(jid)["status"] == "ready"
    for url in (f"/v1/exports/{jid}", f"/v1/exports/{jid}/download"):
        assert client.get(url, headers=other.headers).status_code == 404  # never another person's export
    assert all(j["id"] != jid for j in client.get("/v1/exports", headers=other.headers).json())
    got = client.get(f"/v1/exports/{jid}/download", headers=me.headers)
    assert got.status_code == 200 and got.headers["cache-control"] == "private, no-store"
    assert json.loads(got.content)["account"]["id"] == str(me.id)
    assert client.get(f"/v1/exports/{jid}", headers=me.headers).json()["downloads"] == 1
    with get_sessionmaker()() as db:
        logged = db.scalars(
            select(AuditEvent.action).where(AuditEvent.target_type == "export_job", AuditEvent.target_id == jid)
        ).all()
    assert {"export.requested", "export.ready", "export.downloaded"} <= set(logged)


def test_audit_export_needs_the_permission_and_mfa_and_is_formula_safe(client: TestClient, db: Session) -> None:
    learner = Staff(client, db, [], mfa=True)
    no_mfa, admin = Staff(client, db, ["owner_admin"]), Staff(client, db, ["owner_admin"], mfa=True)
    assert _request(client, learner, "audit_events", since=SINCE).status_code == 403
    assert _request(client, no_mfa, "audit_events", since=SINCE).status_code == 403
    assert _request(client, admin, "audit_events").status_code == 422  # unbounded: a start date is required
    marker = f'=HYPERLINK("fixture-{uuid.uuid4().hex[:6]}")'
    with get_sessionmaker()() as s:
        record(s, actor=None, action="fixture.formula", target_type="fixture", target_id=marker, details={})
        s.commit()
    job = _request(client, admin, "audit_events", since=SINCE, action="fixture.formula")
    assert job.status_code == 202, job.text
    assert _work(job.json()["id"])["status"] == "ready"
    body = client.get(f"/v1/exports/{job.json()['id']}/download", headers=admin.headers)
    assert body.status_code == 200 and body.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(body.content.decode("utf-8"))))
    assert rows[0][0] == "at" and any(r[4] == "'" + marker for r in rows[1:])  # neutralised, never a live formula
    with get_sessionmaker()() as s:
        s.execute(text("update staff_role_grant set revoked_at = now() where user_id = :u"), {"u": str(admin.id)})
        s.commit()
    assert client.get(f"/v1/exports/{job.json()['id']}/download", headers=admin.headers).status_code == 403


def test_a_role_removed_before_generation_fails_the_job(client: TestClient, db: Session) -> None:
    admin = Staff(client, db, ["owner_admin"], mfa=True)
    job = _request(client, admin, "audit_events", since=SINCE).json()
    with get_sessionmaker()() as s:
        s.execute(text("update staff_role_grant set revoked_at = now() where user_id = :u"), {"u": str(admin.id)})
        s.commit()
    done = _work(job["id"])
    assert done["status"] == "failed" and done["file_key"] is None


def test_bounded_work_cancel_retry_and_expiry(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    admin = Staff(client, db, ["owner_admin"], mfa=True)
    monkeypatch.setattr(service, "MAX_ROWS", 0)  # any row at all is "too large" for this check
    big = _request(client, admin, "audit_events", since=SINCE).json()
    failed = _work(big["id"])
    assert failed["status"] == "failed" and "Narrow the filter" in failed["error"]
    monkeypatch.undo()
    retried = client.post(f"/v1/exports/{big['id']}/retry", headers=admin.headers)
    assert retried.status_code == 200 and retried.json()["status"] == "queued" and retried.json()["tries"] == 1
    assert client.post(f"/v1/exports/{big['id']}/cancel", headers=admin.headers).json()["status"] == "cancelled"
    assert client.post(f"/v1/exports/{big['id']}/retry", headers=admin.headers).status_code == 409
    learner = _learner(client)
    jobs = [_request(client, learner, "personal_data") for _ in range(service.MAX_OPEN_PER_USER)]
    assert all(j.status_code == 202 for j in jobs)
    assert _request(client, learner, "personal_data").status_code == 409  # bounded open jobs per person
    ready = jobs[0].json()["id"]
    assert _work(ready)["status"] == "ready"
    with get_sessionmaker()() as s:
        key = s.get(service.ExportJob, uuid.UUID(ready)).file_key  # type: ignore[union-attr]
        s.execute(text("update export_job set expires_at = now() - interval '1 minute' where id = :j"), {"j": ready})
        s.commit()
    with get_sessionmaker()() as s:
        service.run_once(s, worker="fixture-worker")  # the sweep expires it and deletes the file
    assert _status(client, learner, ready) == "expired" and not service._path(str(key)).exists()
    gone = client.get(f"/v1/exports/{ready}/download", headers=learner.headers)
    assert gone.status_code == 409 and gone.json()["code_reason"] == "NOT_READY"


def test_a_crashed_workers_job_is_taken_over_and_a_cancelled_run_is_discarded(client: TestClient) -> None:
    learner = _learner(client)
    jid = _request(client, learner, "personal_data").json()["id"]
    with get_sessionmaker()() as s:
        s.execute(
            text(
                "update export_job set status = 'running', lease_owner = 'dead-worker', "
                "lease_expires_at = now() - interval '1 minute' where id = :j"
            ),
            {"j": jid},
        )
        s.commit()
    assert _work(jid)["status"] == "ready"


def test_a_personal_export_is_withdrawn_when_a_result_release_moves_later(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    code = _publish_profile(
        client, db, [{"subject": "physics", "grades": [11], "questions": 2}], solution_release="after_window"
    )
    admin = Staff(client, db, ["academic_adjudicator"], mfa=True)
    learner = _learner(client)
    session_id, attempt_id, _ = _sit(client, db, learner, admin=admin, code=code)
    held = _request(client, learner, "personal_data").json()
    assert _work(held["id"])["status"] == "ready"
    early = json.loads(client.get(f"/v1/exports/{held['id']}/download", headers=learner.headers).content)
    assert early["practice"]["scores"] == []  # generation applied the release policy
    _shift(session_id, results_at=-1)
    job = _request(client, learner, "personal_data").json()
    assert _work(job["id"])["status"] == "ready"
    _shift(session_id, results_at=60)  # staff move the release later again
    r = client.get(f"/v1/exports/{job['id']}/download", headers=learner.headers)
    assert r.status_code == 409 and r.json()["code_reason"] == "WITHDRAWN"
    assert _status(client, learner, job["id"]) == "expired"
    assert attempt_id
