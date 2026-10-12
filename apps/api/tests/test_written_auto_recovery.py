"""W05.S3.T1 (AUTO-RECOVERY-01): automatic-assessment jobs recover from crashes without double outcomes.

* Reconciliation finds sealed scripts that never got stage records (a crash between sealing and enqueueing, or an
  assessor enabled later) and enqueues them once; running it again adds nothing.
* A worker that dies holding a lease loses it when the lease expires; another worker reclaims the same record (the
  attempt counter shows it) and finishes it. A late result from the dead worker can't replace that outcome.

Uses the deterministic technical fixture assessor (B10: no provider is configured) and fixture scripts; the stage
records created here are removed afterwards.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text

from portal_api.db import get_sessionmaker
from portal_api.modules.written import automatic
from portal_api.modules.written.automatic import AutoAssessment
from tests.test_written_automatic import Scripted
from tests.test_written_marking import _sealed_script


def _count(attempt_id: str, assessor: str) -> int:
    with get_sessionmaker()() as db:
        return int(
            db.scalar(
                select(func.count()).where(
                    AutoAssessment.attempt_id == uuid.UUID(attempt_id), AutoAssessment.assessor == assessor
                )
            )
            or 0
        )


def test_reconciliation_enqueues_a_missed_script_once(client: TestClient, published_written: dict[str, Any]) -> None:
    _, a = _sealed_script(client, published_written["chapter"])
    seen = Scripted(automatic.FixtureAssessor().assess)
    seen.name = f"fx-recon-{uuid.uuid4().hex[:8]}"  # a newly enabled assessor: nothing has been enqueued for it
    assert _count(a["id"], seen.name) == 0
    try:
        with get_sessionmaker()() as db:
            assert automatic.reconcile(db, seen, limit=100_000) >= 1
        first = _count(a["id"], seen.name)
        assert first >= 1
        with get_sessionmaker()() as db:
            assert automatic.reconcile(db, seen, limit=100_000) == 0  # idempotent
        assert _count(a["id"], seen.name) == first
    finally:
        with get_sessionmaker()() as db:
            db.execute(delete(AutoAssessment).where(AutoAssessment.assessor == seen.name))
            db.commit()


def test_a_stale_lease_is_reclaimed_and_a_late_result_cannot_replace_the_outcome(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    _, a = _sealed_script(client, published_written["chapter"])
    seen = Scripted(automatic.FixtureAssessor().assess)
    seen.name = f"fx-lease-{uuid.uuid4().hex[:8]}"
    try:
        with get_sessionmaker()() as db:
            assert automatic.enqueue(db, uuid.UUID(a["id"]), seen) >= 1
            db.commit()
            db.execute(  # make this script's records the next to be claimed in the shared test queue
                text("update written_auto_assessment set next_attempt_at = '2000-01-01' where assessor = :n"),
                {"n": seen.name},
            )
            db.commit()
        with get_sessionmaker()() as db:
            dead = automatic._claim(db)  # worker A claims, then dies without finishing
            assert dead is not None and str(dead.attempt_id) == a["id"] and dead.attempts == 1
            dead_id = dead.id
            db.execute(
                text("update written_auto_assessment set lease_expires_at = now() - interval '1 minute' where id = :i"),
                {"i": dead_id},
            )
            db.commit()
        with get_sessionmaker()() as db:
            again = automatic._claim(db)  # worker B reclaims the expired lease
            assert again is not None and again.id == dead_id and again.attempts == 2 and again.status == "running"
            outcome = automatic.process(db, again.id, seen)
            assert outcome in ("proposed", "review", "rejected")
        with get_sessionmaker()() as db:
            late = automatic._finish(db, dead_id, "rejected", errors=["Fixture: a late result from worker A"])
            assert late == outcome  # the first finished outcome stands
            row = db.get(AutoAssessment, dead_id)
            assert row is not None and row.status == outcome and "Fixture: a late result" not in str(row.errors)
    finally:
        with get_sessionmaker()() as db:
            db.execute(delete(AutoAssessment).where(AutoAssessment.assessor == seen.name))
            db.commit()
