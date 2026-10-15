"""W04.S2.T3 (CUTOFF-RACES-01): the upload cutoff U under contention. Admission is decided on the database clock read
after the attempt lock is taken (lock-then-clock), so a submission that waits for the lock past U is refused; U itself
is still admitted; the expiry worker never waits on a locked attempt and never touches a sealed one; a learner may
submit early. Technical fixtures only; timings use one-second margins."""

from __future__ import annotations

import threading
import time
import uuid
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select, text

from portal_api.db import get_sessionmaker
from portal_api.modules.written import service
from portal_api.modules.written.models import WrittenAttempt
from tests.test_written_attempts import _learner, _map, _png, _seal, _shift, _start, _upload


def _ready(client: TestClient, chapter: str, seed: int, **extra: Any) -> tuple[Any, dict[str, Any], int]:
    """An attempt with one page mapped to both parts, ready to submit."""
    who = _learner(client)
    a = _start(client, who, chapter, **extra)
    page = _upload(client, who, a["id"], _png(seed=seed)).json()["pages"][0]["id"]
    m = _map(client, who, a, {"1:a": {"pages": [page]}, "1:b": {"pages": [page]}}).json()
    return who, a, m["manifest_revision"]


def _status(attempt_id: str) -> str:
    with get_sessionmaker()() as db:
        return str(db.execute(text("select status from written_attempt where id = :i"), {"i": attempt_id}).scalar_one())


def test_the_cutoff_instant_itself_is_admitted_and_a_microsecond_later_is_not(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    _, a, _ = _ready(client, published_written["chapter"], seed=531)
    with get_sessionmaker()() as db:
        attempt = db.scalar(select(WrittenAttempt).where(WrittenAttempt.id == uuid.UUID(a["id"])).with_for_update())
        assert attempt is not None
        u = attempt.upload_cutoff_at
        assert service._expire_if_due(db, attempt, u) is False and attempt.status == "active"  # at U: still open
        assert service._expire_if_due(db, attempt, u + timedelta(microseconds=1)) is True
        assert attempt.status == "expired"
        db.rollback()  # a probe of the rule only; nothing is kept
    assert _status(a["id"]) == "active"


def test_a_submission_that_waits_for_the_lock_past_the_cutoff_is_refused(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    who, a, revision = _ready(client, published_written["chapter"], seed=532)
    _shift(a["id"], cutoff_offset_s=1.0)  # U is one second away
    holder = get_sessionmaker()()
    holder.execute(text("select id from written_attempt where id = :i for update"), {"i": a["id"]})  # e.g. an upload
    result: dict[str, Any] = {}

    def submit() -> None:
        result["response"] = _seal(client, who, a["id"], revision)

    worker = threading.Thread(target=submit)
    worker.start()  # it starts before U and blocks on the attempt lock
    time.sleep(2.0)  # the lock is held past U
    assert worker.is_alive(), "the submission should still be waiting for the lock"
    holder.rollback()
    holder.close()
    worker.join(timeout=30)
    late = result["response"]
    assert late.status_code == 409 and late.json()["attempt_status"] == "expired"  # the clock was read after the lock
    assert _status(a["id"]) == "expired"


def test_the_expiry_worker_skips_a_locked_attempt_and_never_touches_a_sealed_one(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    _, waiting, _ = _ready(client, published_written["chapter"], seed=533)
    who, sealed, revision = _ready(client, published_written["chapter"], seed=534)
    assert _seal(client, who, sealed["id"], revision).status_code == 200
    _shift(waiting["id"], cutoff_offset_s=-1.0)
    _shift(sealed["id"], cutoff_offset_s=-1.0)  # past U for both

    holder = get_sessionmaker()()
    holder.execute(text("select id from written_attempt where id = :i for update"), {"i": waiting["id"]})
    try:
        started = time.monotonic()
        with get_sessionmaker()() as db:
            service.expire_due(db)
        assert time.monotonic() - started < 5  # skipped, not waited for
        assert _status(waiting["id"]) == "active"  # whoever holds it decides; the worker comes back later
    finally:
        holder.rollback()
        holder.close()
    with get_sessionmaker()() as db:
        service.expire_due(db)
    assert _status(waiting["id"]) == "expired"
    assert _status(sealed["id"]) == "sealed"  # a receipt is final: expiry never undoes it
    with get_sessionmaker()() as db:
        receipts = db.execute(text("select count(*) from written_receipt where attempt_id = :i"), {"i": sealed["id"]})
        assert receipts.scalar_one() == 1


def test_a_learner_may_submit_before_writing_time_ends(client: TestClient, published_written: dict[str, Any]) -> None:
    who, a, revision = _ready(client, published_written["chapter"], seed=535, writing_minutes=20)
    sealed = _seal(client, who, a["id"], revision)
    assert sealed.status_code == 200, sealed.text
    with get_sessionmaker()() as db:
        admitted, deadline = db.execute(
            text(
                "select r.admitted_at, a.writing_deadline_at from written_receipt r "
                "join written_attempt a on a.id = r.attempt_id where a.id = :i"
            ),
            {"i": a["id"]},
        ).one()
    assert admitted < deadline  # submitted early, and final
    assert _upload(client, who, a["id"], _png(seed=536)).status_code == 409
