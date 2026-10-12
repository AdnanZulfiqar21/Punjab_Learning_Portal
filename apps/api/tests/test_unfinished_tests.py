"""P19.S1.T1 (JOURNEYS-01): a test started on one device can be found and finished on another.

The dashboard lists the learner's unfinished tests (practice, mock and written) until they are submitted or their
time is up, newest first, with progress and closing time. Nobody else sees them. Fixture questions and accounts only.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from portal_api.db import get_sessionmaker
from tests.test_attempts import POOL, _form, _learner, _op, _save_ops, _start
from tests.test_mcq_corrections import _keys
from tests.test_written_attempts import _start as _start_written

URL = "/v1/me/dashboard"


def _unfinished(client: TestClient, who: Any) -> list[dict[str, Any]]:
    r = client.get(URL, headers=who.headers)
    assert r.status_code == 200, r.text
    return list(r.json()["unfinished"])


def test_unfinished_tests_are_listed_until_submitted_or_out_of_time(
    client: TestClient, physics: dict[str, Any], published_written: dict[str, Any]
) -> None:
    learner, other = _learner(client), _learner(client)
    assert _unfinished(client, learner) == []
    form = _form(client, learner, physics["chapter"], count=POOL).json()
    attempt = _start(client, learner, form["id"])
    keys = _keys(form["id"])
    assert _save_ops(client, learner, attempt["id"], _op(1, 1, keys[1]), _op(2, 1, keys[2])).status_code == 200
    written = _start_written(client, learner, published_written["chapter"])

    listed = _unfinished(client, learner)
    assert [u["attempt_id"] for u in listed] == [written["id"], attempt["id"]]  # newest first
    practice = listed[1]
    assert (practice["kind"], practice["grade"], practice["subject"]) == ("practice", 11, "physics")
    assert (practice["answered"], practice["questions"]) == (2, POOL)
    assert listed[0]["kind"] == "written" and listed[0]["answered"] is None and listed[0]["closes_at"]
    assert _unfinished(client, other) == []  # only the learner's own

    # Submitted: gone. Out of time but not yet closed by the background job: gone too.
    done = client.post(
        f"/v1/attempts/{attempt['id']}/submit",
        headers=learner.headers,
        json={"idempotency_key": uuid.uuid4().hex, "ops": []},
    )
    assert done.status_code == 200
    with get_sessionmaker()() as db:
        db.execute(
            text("update written_attempt set upload_cutoff_at = now() - interval '1 minute' where id = :a"),
            {"a": written["id"]},
        )
        db.commit()
    assert _unfinished(client, learner) == []
