"""W06.S3.T1 (QUEUE-AGEING-01): operators see how long queued written reviews have waited, per class and subject.

The backlog row counts queued cases waiting under 24 hours, 24 to 48 hours and over 48 hours (the proposed service
targets in §20.10) and the time the longest-waiting case opened. Technical fixture scripts; their timestamps are
restored afterwards.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from tests.test_operations import _operator
from tests.test_written_marking import _sealed_script


def _row(client: TestClient, who: Any) -> dict[str, Any]:
    rows = client.get("/v1/ops/written-backlog", headers=who.headers).json()
    return next(r for r in rows if (r["grade"], r["subject"]) == (12, "chemistry"))


def _case_of(attempt_id: str) -> str:
    with get_sessionmaker()() as db:
        return str(
            db.execute(
                text("select id from written_review_case where attempt_id = :a and status = 'queued'"),
                {"a": attempt_id},
            ).scalar_one()
        )


def _age(case_id: str, hours: int) -> None:
    with get_sessionmaker()() as db:
        db.execute(
            text("update written_review_case set opened_at = now() - make_interval(hours => :h) where id = :c"),
            {"h": hours, "c": case_id},
        )
        db.commit()


def test_queued_reviews_are_counted_by_how_long_they_have_waited(
    client: TestClient, published_written: dict[str, Any]
) -> None:
    operator = _operator(client)
    _, a = _sealed_script(client, published_written["chapter"])
    _, b = _sealed_script(client, published_written["chapter"])
    first, second = _case_of(a["id"]), _case_of(b["id"])
    before = _row(client, operator)
    try:
        _age(first, 30)
        _age(second, 60)
        after = _row(client, operator)
        assert after["queued_under_24h"] == before["queued_under_24h"] - 2
        assert after["queued_24_to_48h"] == before["queued_24_to_48h"] + 1
        assert after["queued_over_48h"] == before["queued_over_48h"] + 1
        oldest = datetime.fromisoformat(after["oldest_queued_at"])
        assert (datetime.now(oldest.tzinfo) - oldest).total_seconds() >= 60 * 3600 - 60
        assert client.get("/v1/ops/written-backlog", headers=_operator(client, mfa=False).headers).status_code == 403
    finally:
        _age(first, 0)
        _age(second, 0)
