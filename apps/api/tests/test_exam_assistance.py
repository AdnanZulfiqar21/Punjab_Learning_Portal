"""P10.S4.T3 (EXAM-ROOM-01): no answers or explanations through other routes while a mock is running.

While a learner's mock attempt is open (before its cutoff), the routes that would reveal keys or explanations are
refused with MOCK_IN_PROGRESS: new practice, review and mock tests, other attempts (opening, answering, submitting),
other results, the mistake notebook and offline study packs. The running mock itself works normally, and everything
opens again once it is submitted. Lessons stay readable: the platform can't stop someone opening a book, so it
doesn't claim to. Questions and accounts are labelled technical fixtures.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_attempts import _form, _learner, _op, _save_ops, _start
from tests.test_mcq_corrections import _keys
from tests.test_mocks import _mock, _publish_profile


def _refused(r: Any) -> bool:
    return bool(r.status_code == 409 and r.json().get("code_reason") == "MOCK_IN_PROGRESS")


def test_a_running_mock_locks_every_route_that_could_reveal_answers(
    client: TestClient, db: Session, physics: dict[str, Any]
) -> None:
    learner = _learner(client)
    # Before the mock: one finished practice test (with a result) and one open immediate-feedback practice test.
    done_form = _form(client, learner, physics["chapter"], count=2).json()
    done = _start(client, learner, done_form["id"])
    client.post(
        f"/v1/attempts/{done['id']}/submit",
        headers=learner.headers,
        json={"idempotency_key": uuid.uuid4().hex, "ops": []},
    )
    open_form = _form(client, learner, physics["chapter"], count=2, feedback_mode="immediate").json()
    open_attempt = _start(client, learner, open_form["id"])

    code = _publish_profile(client, db, [{"subject": "physics", "grades": [11], "questions": 2}])
    mock_form = _mock(client, learner, code).json()
    mock = _start(client, learner, mock_form["id"])
    h = learner.headers

    refused = {
        "new practice test": _form(client, learner, physics["chapter"], count=1),
        "another mock": _mock(client, learner, code),
        "review test": client.post(
            "/v1/me/notebook/review",
            headers={**h, "Idempotency-Key": uuid.uuid4().hex},
            json={"grade": 11, "subject": "physics"},
        ),
        "open another attempt": client.get(f"/v1/attempts/{open_attempt['id']}", headers=h),
        "start another attempt": client.post(f"/v1/practice/forms/{open_form['id']}/attempt", headers=h),
        "answer with feedback": _save_ops(client, learner, open_attempt["id"], _op(1, 1, "o1")),
        "another result": client.get(f"/v1/attempts/{done['id']}/result", headers=h),
        "mistake notebook": client.get("/v1/me/notebook", headers=h),
        "offline study pack": client.get(f"/v1/me/study-packs/{physics['chapter']}", headers=h),
    }
    for name, r in refused.items():
        assert _refused(r), (name, r.status_code, r.text[:200])
    # The mock itself carries on normally.
    assert client.get(f"/v1/attempts/{mock['id']}", headers=h).status_code == 200
    keys = _keys(mock_form["id"])
    assert _save_ops(client, learner, mock["id"], *[_op(p, 1, k) for p, k in keys.items()]).status_code == 200
    submitted = client.post(
        f"/v1/attempts/{mock['id']}/submit", headers=h, json={"idempotency_key": uuid.uuid4().hex, "ops": []}
    )
    assert submitted.status_code == 200

    # Submitted: everything opens again.
    assert client.get(f"/v1/attempts/{done['id']}/result", headers=h).status_code == 200
    assert client.get("/v1/me/notebook", headers=h).status_code == 200
    assert client.get(f"/v1/attempts/{open_attempt['id']}", headers=h).status_code == 200
    assert _form(client, learner, physics["chapter"], count=1).status_code == 201
    assert client.get(f"/v1/attempts/{mock['id']}/result", headers=h).status_code == 200
